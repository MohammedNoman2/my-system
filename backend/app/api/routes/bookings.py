from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, require_booking_role
from app.core.database import get_db
from app.core.config import office_today
from app.models.booking import Booking, BookingStatus, BookingType
from app.models.booking_details import (
    FlightBookingDetail,
    ParcelBookingDetail,
    PassportBookingDetail,
    TransportBookingDetail,
    TransportInfant,
    VisaBookingDetail,
)
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.accounting import Account, JournalEntry, JournalEntryLine
from app.models.financial import EntityType, FinancialTransaction, PaymentMethod, TransactionType
from app.models.settings import Settings
from app.models.user import User, UserRole
from app.schemas.booking import (
    BookingAdminResponse,
    BookingCancelRequest,
    BookingCreate,
    BookingEmployeeResponse,
    BookingPostponeRequest,
    BookingRerouteRequest,
    TicketSearchItem,
    TicketSearchResponse,
    TransportBatchCreate,
)
from app.services.counter_service import get_next_reference_number
from app.services.print_service import generate_voucher_html, generate_voucher_pdf
from app.services.accounting_service import (
    AccountingMismatchException,
    create_entity_accounts,
    create_journal_entry,
    get_account_by_code,
    get_customer_available_credit,
    get_entity_account,
    get_entity_balance,
    get_payment_channel_account,
)
from app.services.shift_service import get_active_shift
from app.utils.audit import log_audit_event

router = APIRouter(prefix="/bookings", tags=["Bookings"])

PREFIX_MAP = {
    BookingType.FLIGHT: "FL",
    BookingType.TRANSPORT: "TR",
    BookingType.VISA: "VI",
    BookingType.PASSPORT: "PA",
    BookingType.PARCEL: "PR",
}


def format_booking_response(full_booking: Booking, role: UserRole):
    creator_name = full_booking.employee.full_name if full_booking.employee else "مدير النظام"
    creator_id = full_booking.employee_id
    if role == UserRole.EMPLOYEE:
        resp = BookingEmployeeResponse.model_validate(full_booking)
        resp.created_by_id = creator_id
        resp.created_by_name = creator_name
        return resp
    resp = BookingAdminResponse.model_validate(full_booking)
    resp.created_by_id = creator_id
    resp.created_by_name = creator_name
    return resp


def check_employee_24h_window(booking: Booking, current_user: User, action_label: str = "تعديل أو إلغاء"):
    """Enforces the 24-hour modification/cancellation window for EMPLOYEE role."""
    if current_user.role == UserRole.EMPLOYEE and booking.created_at:
        created_dt = booking.created_at
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        elapsed_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600.0
        if elapsed_hours > 24.0:
            raise HTTPException(
                status_code=403,
                detail=f"لا يمكن للموظف {action_label} الحجز بعد مرور 24 ساعة على إنشائه؛ يرجى مراجعة مدير النظام",
            )


async def _create_booking_core(
    data: BookingCreate,
    request: Request,
    current_user: User,
    db: AsyncSession,
    *,
    commit: bool = True,
) -> Booking:
    # Determine reference prefix and generate next reference number atomically
    prefix = PREFIX_MAP.get(data.type, "BK")
    ref_num = await get_next_reference_number(db, prefix)

    # Resolve or create Customer
    customer = None
    if data.customer_id:
        c_res = await db.execute(select(Customer).where(Customer.id == data.customer_id))
        customer = c_res.scalar_one_or_none()

    if not customer:
        cust_name = ""
        cust_phone = ""
        cust_passport = None
        cust_id = None
        birth_date = None
        birth_place = ""

        if data.type == BookingType.FLIGHT and data.flight_details:
            cust_name = data.flight_details.passenger_name
            cust_phone = data.flight_details.passenger_phone
            cust_passport = data.flight_details.passport_number
            birth_date = data.flight_details.birth_date
            birth_place = data.flight_details.birth_place
        elif data.type == BookingType.TRANSPORT and data.transport_details:
            cust_name = data.transport_details.passenger_name
            cust_phone = data.transport_details.passenger_phone
            cust_id = data.transport_details.id_number
            birth_date = data.transport_details.birth_date
            birth_place = data.transport_details.birth_place
        elif data.type == BookingType.VISA and data.visa_details:
            cust_name = data.visa_details.applicant_name
            cust_phone = data.visa_details.applicant_phone
            cust_passport = data.visa_details.passport_number
            birth_date = data.visa_details.birth_date
            birth_place = data.visa_details.birth_place
        elif data.type == BookingType.PASSPORT and data.passport_details:
            cust_name = data.passport_details.applicant_name
            cust_phone = data.passport_details.applicant_phone
            cust_id = data.passport_details.id_number
            birth_date = data.passport_details.birth_date
            birth_place = data.passport_details.birth_place
        elif data.type == BookingType.PARCEL and data.parcel_details:
            cust_name = data.parcel_details.sender_name
            cust_phone = data.parcel_details.sender_phone

        import re

        def _norm_arabic_tokens(text: str) -> list[str]:
            s = (text or "").strip()
            s = re.sub(r"[أإآ]", "ا", s)
            s = s.replace("ة", "ه").replace("ى", "ي")
            s = re.sub(r"عبد\s+", "عبد", s)
            return [w for w in re.sub(r"\s+", " ", s).lower().split(" ") if w]

        def _names_compatible(name_a: str, name_b: str, strict: bool = False) -> bool:
            ta = _norm_arabic_tokens(name_a)
            tb = _norm_arabic_tokens(name_b)
            if not ta or not tb:
                return False
            if ta == tb:
                return True
            if ta[0] != tb[0]:
                return False
            short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
            if set(short) <= set(long_):
                return True
            if strict:
                return False
            return len(set(ta) & set(tb)) >= min(2, len(ta), len(tb))

        cust_name = re.sub(r"\s+", " ", (cust_name or "").strip())
        cust_phone = re.sub(r"\D", "", (cust_phone or "").strip())
        if cust_phone.startswith("00967") and len(cust_phone) == 14:
            cust_phone = cust_phone[5:]
        elif cust_phone.startswith("967") and len(cust_phone) == 12:
            cust_phone = cust_phone[3:]
        cust_passport = cust_passport.strip().upper() if cust_passport and cust_passport.strip() else None
        cust_id = cust_id.strip() if cust_id and cust_id.strip() else None

        if not cust_name or len(cust_phone) < 9:
            raise HTTPException(
                status_code=400,
                detail="اسم المسافر ورقم الهاتف الصحيح (9 أرقام على الأقل) مطلوبان لإتمام الحجز",
            )

        # 1. Search by national_id OR passport_number with Arabic name compatibility check (prevents P2 silent merge)
        if cust_id:
            c_res = await db.execute(select(Customer).where(Customer.id_number == cust_id))
            doc_match = c_res.scalars().first()
            if doc_match:
                if not _names_compatible(doc_match.name, cust_name, strict=False):
                    raise HTTPException(
                        status_code=409,
                        detail=f"رقم الهوية ({cust_id}) مسجل مسبقاً لعميل آخر باسم مختلف ({doc_match.name}). يرجى التحقق من رقم الهوية أو اختيار العميل الصحيح.",
                    )
                customer = doc_match

        if not customer and cust_passport:
            c_res = await db.execute(select(Customer).where(Customer.passport_number == cust_passport))
            doc_match = c_res.scalars().first()
            if doc_match:
                if not _names_compatible(doc_match.name, cust_name, strict=False):
                    raise HTTPException(
                        status_code=409,
                        detail=f"رقم الجواز ({cust_passport}) مسجل مسبقاً لعميل آخر باسم مختلف ({doc_match.name}). يرجى التحقق من رقم الجواز أو اختيار العميل الصحيح.",
                    )
                customer = doc_match

        # 2. If not found by document, search by phone_number and check strict subset name compatibility
        if not customer:
            phone_res = await db.execute(select(Customer).where(Customer.phone_number == cust_phone))
            same_phone_customers = phone_res.scalars().all()
            for cand in same_phone_customers:
                if _names_compatible(cand.name, cust_name, strict=True):
                    customer = cand
                    break

        # 3. If matched, update missing passport/id if not conflicting; else create new customer record
        if customer:
            if cust_passport and not customer.passport_number:
                customer.passport_number = cust_passport
            if cust_id and not customer.id_number:
                customer.id_number = cust_id
            await create_entity_accounts(db, "customer", customer.id, customer.name)
        else:
            customer = Customer(
                name=cust_name,
                phone_number=cust_phone,
                passport_number=cust_passport,
                id_number=cust_id,
                balance=Decimal("0.00"),
            )
            db.add(customer)
            await db.flush()
            await create_entity_accounts(db, "customer", customer.id, customer.name)
    else:
        # Ensure entity sub-accounts exist
        await create_entity_accounts(db, "customer", customer.id, customer.name)

    curr_str = (data.currency or "YER").upper()
    selling_price_dec = Decimal(str(data.selling_price)).quantize(Decimal("0.01"))
    cash_paid_dec = Decimal(str(data.paid_amount or 0)).quantize(Decimal("0.01"))

    if cash_paid_dec > selling_price_dec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المبلغ المدفوع أكبر من سعر البيع",
        )

    # P6: Check and consume available unapplied credit balance for customer in booking currency
    avail_credit = Decimal("0.00")
    if getattr(data, "use_credit_balance", True):
        avail_credit = await get_customer_available_credit(db, customer.id, curr_str)

    unpaid_after_cash = selling_price_dec - cash_paid_dec
    credit_applied = min(avail_credit, unpaid_after_cash).quantize(Decimal("0.01"))
    effective_paid_amount = (cash_paid_dec + credit_applied).quantize(Decimal("0.01"))
    remaining_amount = (selling_price_dec - effective_paid_amount).quantize(Decimal("0.01"))

    booking_notes = data.notes
    if credit_applied > Decimal("0.00"):
        credit_note = f"[تم خصم {credit_applied} {curr_str} من الرصيد الدائن المتاح للعميل]"
        booking_notes = f"{booking_notes} | {credit_note}" if booking_notes else credit_note

    # Resolve Supplier (Support Manual Free-Text Entry with Ledger Account Auto-Creation)
    resolved_supplier_id = data.supplier_id
    if data.supplier_name and data.supplier_name.strip():
        s_name = data.supplier_name.strip()
        supp_res = await db.execute(
            select(Supplier).where(func.lower(func.trim(Supplier.name)) == s_name.lower())
        )
        found_supp = supp_res.scalars().first()
        if found_supp:
            resolved_supplier_id = found_supp.id
        else:
            new_supp = Supplier(
                name=s_name,
                phone_number=f"77000{ref_num}",
                service_type=data.type.value if hasattr(data.type, "value") else str(data.type),
            )
            db.add(new_supp)
            await db.flush()
            await create_entity_accounts(db, "supplier", new_supp.id, s_name)
            resolved_supplier_id = new_supp.id

    # Role check on cost_price
    cost_price = data.cost_price if current_user.role != UserRole.EMPLOYEE else Decimal("0.00")

    booking = Booking(
        booking_id=ref_num,
        ticket_number=ref_num,
        type=data.type,
        customer_id=customer.id,
        employee_id=current_user.id,
        cost_price=cost_price,
        selling_price=selling_price_dec,
        paid_amount=effective_paid_amount,
        credit_applied=credit_applied,
        remaining_amount=remaining_amount,
        currency=curr_str,
        supplier_id=resolved_supplier_id,
        notes=booking_notes,
        status=BookingStatus.CONFIRMED if effective_paid_amount > Decimal("0.00") else BookingStatus.PENDING,
    )
    db.add(booking)
    await db.flush()

    # Create sub-details
    if data.type == BookingType.FLIGHT:
        if not data.flight_details:
            raise HTTPException(status_code=400, detail="بيانات رحلة الطيران مطلوبة")
        fd = FlightBookingDetail(
            booking_id=booking.id,
            airline_company=data.flight_details.airline_company,
            flight_number=data.flight_details.flight_number,
            departure_airport=data.flight_details.departure_airport,
            arrival_airport=data.flight_details.arrival_airport,
            departure_date=data.flight_details.departure_date,
            departure_time=data.flight_details.departure_time,
            return_date=data.flight_details.return_date,
            return_time=data.flight_details.return_time,
            ticket_type=data.flight_details.ticket_type,
            allowed_weight=data.flight_details.allowed_weight,
            passenger_name=data.flight_details.passenger_name,
            passenger_phone=data.flight_details.passenger_phone,
            passport_number=data.flight_details.passport_number,
            birth_date=data.flight_details.birth_date,
            birth_place=data.flight_details.birth_place,
            passport_image_url=data.flight_details.passport_image_url,
        )
        db.add(fd)

    elif data.type == BookingType.TRANSPORT:
        if not data.transport_details:
            raise HTTPException(status_code=400, detail="بيانات النقل البري مطلوبة")
        td = TransportBookingDetail(
            booking_id=booking.id,
            transport_company=data.transport_details.transport_company,
            departure_station=data.transport_details.departure_station,
            arrival_station=data.transport_details.arrival_station,
            travel_date=data.transport_details.travel_date,
            travel_time=data.transport_details.travel_time,
            passenger_name=data.transport_details.passenger_name,
            first_middle_name=data.transport_details.first_middle_name,
            last_name=data.transport_details.last_name,
            passenger_phone=data.transport_details.passenger_phone,
            id_type=data.transport_details.id_type or "national_id",
            id_number=data.transport_details.id_number or "",
            birth_date=data.transport_details.birth_date,
            birth_place=data.transport_details.birth_place,
            id_image_url=data.transport_details.id_image_url,
        )
        db.add(td)
        for inf in getattr(data.transport_details, "infants", []) or []:
            db.add(TransportInfant(
                booking_id=booking.id,
                full_name=inf.full_name,
                id_type=inf.id_type,
                id_number=inf.id_number or "",
                birth_date=inf.birth_date,
            ))

    elif data.type == BookingType.VISA:
        if not data.visa_details:
            raise HTTPException(status_code=400, detail="بيانات طلب التأشيرة مطلوبة")
        vd = VisaBookingDetail(
            booking_id=booking.id,
            visa_type=data.visa_details.visa_type,
            application_date=data.visa_details.application_date,
            applicant_name=data.visa_details.applicant_name,
            applicant_phone=data.visa_details.applicant_phone,
            passport_number=data.visa_details.passport_number,
            birth_date=data.visa_details.birth_date,
            birth_place=data.visa_details.birth_place,
            passport_image_url=data.visa_details.passport_image_url,
        )
        db.add(vd)

    elif data.type == BookingType.PASSPORT:
        if not data.passport_details:
            raise HTTPException(status_code=400, detail="بيانات معاملة الجواز مطلوبة")
        pd = PassportBookingDetail(
            booking_id=booking.id,
            passport_type=data.passport_details.passport_type,
            priority=data.passport_details.priority,
            application_date=data.passport_details.application_date,
            expected_delivery_date=data.passport_details.expected_delivery_date,
            applicant_name=data.passport_details.applicant_name,
            applicant_phone=data.passport_details.applicant_phone,
            id_number=data.passport_details.id_number,
            birth_date=data.passport_details.birth_date,
            birth_place=data.passport_details.birth_place,
            id_image_url=data.passport_details.id_image_url,
        )
        db.add(pd)

    elif data.type == BookingType.PARCEL:
        if not data.parcel_details:
            raise HTTPException(status_code=400, detail="بيانات شحن الطرد مطلوبة")
        pld = ParcelBookingDetail(
            booking_id=booking.id,
            sender_name=data.parcel_details.sender_name,
            sender_phone=data.parcel_details.sender_phone,
            receiver_name=data.parcel_details.receiver_name,
            receiver_phone=data.parcel_details.receiver_phone,
            delivery_destination=data.parcel_details.delivery_destination,
            parcel_type=data.parcel_details.parcel_type,
            weight=data.parcel_details.weight,
            content_description=data.parcel_details.content_description,
            shipping_date=data.parcel_details.shipping_date,
        )
        db.add(pld)

    # 3. P5: Generate Full Accrual JournalEntry on Customer Account (full selling_price)
    je_ref = await get_next_reference_number(db, "JE")

    cash_acc = await get_account_by_code(db, f"1101-{curr_str}")
    cust_acc = await get_entity_account(db, "customer", customer.id, curr_str, customer.name)
    sales_acc = await get_account_by_code(db, f"4101-{curr_str}")

    je_lines = [
        {"account_id": cust_acc.id, "debit": selling_price_dec, "credit": Decimal("0.0000")},
        {"account_id": sales_acc.id, "debit": Decimal("0.0000"), "credit": selling_price_dec},
    ]

    if cost_price > 0 and resolved_supplier_id:
        cogs_acc = await get_account_by_code(db, f"5101-{curr_str}")
        supp_acc = await get_entity_account(db, "supplier", resolved_supplier_id, curr_str)
        je_lines.append({"account_id": cogs_acc.id, "debit": cost_price, "credit": Decimal("0.0000")})
        je_lines.append({"account_id": supp_acc.id, "debit": Decimal("0.0000"), "credit": cost_price})

    accrual_desc = f"قيد حجز {ref_num} - {data.type.value} - العميل: {customer.name} (إجمالي القيمة: {selling_price_dec} {curr_str})"
    if credit_applied > Decimal("0.00"):
        accrual_desc += f" [شمل خصم رصيد دائن متاح: {credit_applied} {curr_str}]"

    await create_journal_entry(
        session=db,
        entry_number=je_ref,
        reference_type="BOOKING",
        reference_id=ref_num,
        currency=curr_str,
        description=accrual_desc,
        lines_data=je_lines,
    )

    # 4. P5 & 5-A2: If cash_paid_dec > 0, route to 1101 (cash + shift) or 1102 (bank/check without cash shift)
    if cash_paid_dec > Decimal("0.00"):
        pm_val = getattr(data, "payment_method", PaymentMethod.CASH) or PaymentMethod.CASH
        ref_doc = (getattr(data, "reference_number", None) or "").strip() or None
        active_shift = (
            await get_active_shift(db, current_user.id, raise_if_none=False)
            if pm_val == PaymentMethod.CASH
            else None
        )
        channel_acc = await get_payment_channel_account(db, pm_val, curr_str)
        rc_ref = await get_next_reference_number(db, "RC")
        payment_record = FinancialTransaction(
            transaction_id=rc_ref,
            type=TransactionType.PAYMENT_IN,
            entity_type=EntityType.CUSTOMER,
            entity_id=customer.id,
            amount=cash_paid_dec,
            currency=curr_str,
            payment_method=pm_val,
            reference_number=ref_doc,
            notes=f"دفعة مقدمة لحجز {ref_num}",
            transaction_date=office_today(),
            booking_id=booking.id,
            created_by=current_user.id,
            shift_id=active_shift.id if active_shift else None,
        )
        db.add(payment_record)
        await db.flush()

        rc_je_ref = await get_next_reference_number(db, "JE")
        await create_journal_entry(
            session=db,
            entry_number=rc_je_ref,
            reference_type="RECEIPT",
            reference_id=rc_ref,
            currency=curr_str,
            description=f"سند قبض دفعة مقدمة {rc_ref} لحجز {ref_num} - العميل: {customer.name}",
            lines_data=[
                {"account_id": channel_acc.id, "debit": cash_paid_dec, "credit": Decimal("0.0000")},
                {"account_id": cust_acc.id, "debit": Decimal("0.0000"), "credit": cash_paid_dec},
            ],
        )

    # Sync dynamic balance (unified base currency across all sub-accounts)
    customer.balance = await get_entity_balance(db, "customer", customer.id)
    if resolved_supplier_id:
        supp_obj = await db.get(Supplier, resolved_supplier_id)
        if supp_obj:
            supp_obj.balance = await get_entity_balance(db, "supplier", supp_obj.id)

    await log_audit_event(
        db,
        "INSERT",
        "bookings",
        user=current_user,
        record_id=booking.id,
        new_data={"booking_id": ref_num, "type": data.type.value, "selling_price": float(data.selling_price)},
        request=request,
    )

    if commit:
        await db.commit()
    else:
        await db.flush()
    return booking


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_booking(
    data: BookingCreate,
    request: Request,
    current_user: User = Depends(require_booking_role),
    db: AsyncSession = Depends(get_db),
):
    booking = await _create_booking_core(data, request, current_user, db, commit=True)

    # Re-fetch with relationships for output
    stmt = (
        select(Booking)
        .where(Booking.id == booking.id)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.employee),
            selectinload(Booking.supplier),
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.visa_details),
            selectinload(Booking.passport_details),
            selectinload(Booking.parcel_details),
        )
    )
    res = await db.execute(stmt)
    full_booking = res.scalar_one()

    return format_booking_response(full_booking, current_user.role)


@router.post("/transport-batch", status_code=status.HTTP_201_CREATED)
async def create_transport_batch(
    data: TransportBatchCreate,
    request: Request,
    current_user: User = Depends(require_booking_role),
    db: AsyncSession = Depends(get_db),
):
    """
    إنشاء عدة مقاعد نقل بري دفعة واحدة ذرّية بالكامل (Atomic Transaction):
    - تذكرة مستقلة (TR-XXXX) وقيد استحقاق (BOOKING) مستقل لكل مسافر.
    - فحص سقف المدفوع مقابل مجموع المتبقي الفعلي بعد خصم الرصيد الدائن.
    - سند قبض واحد (RC-XXXX) وقيد قبض واحد (RECEIPT) لإجمالي المدفوع،
      موزع بالتساوي عبر VoucherAllocation (مع سقف remaining_amount لكل مقعد وكسر التقريب على الأخير).
    """
    from decimal import ROUND_DOWN
    from app.models.voucher_allocation import VoucherAllocation
    from app.models.accounting import AccountCurrency

    n_seats = len(data.passengers)
    curr_str = (data.currency or "YER").upper()
    selling_per_seat = Decimal(str(data.selling_price)).quantize(Decimal("0.01"))
    cost_per_seat = (
        Decimal("0.00")
        if current_user.role == UserRole.EMPLOYEE
        else Decimal(str(data.cost_price or 0)).quantize(Decimal("0.01"))
    )
    total_paid = Decimal(str(data.paid_amount or 0)).quantize(Decimal("0.01"))

    # 1. Create each TR booking atomically (commit=False) with paid_amount=0 first
    created_bookings: List[Booking] = []
    for p_detail in data.passengers:
        single_req = BookingCreate(
            type=BookingType.TRANSPORT,
            customer_id=data.customer_id,
            cost_price=cost_per_seat,
            selling_price=selling_per_seat,
            paid_amount=Decimal("0.00"),
            currency=curr_str,
            supplier_id=data.supplier_id,
            supplier_name=data.supplier_name,
            notes=data.notes,
            use_credit_balance=data.use_credit_balance,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            transport_details=p_detail,
        )
        bk = await _create_booking_core(
            data=single_req,
            request=request,
            current_user=current_user,
            db=db,
            commit=False,
        )
        created_bookings.append(bk)

    # 2. Validate total_paid against actual total_remaining AFTER credit_balance consumption
    total_remaining = sum(
        (Decimal(str(b.remaining_amount)) for b in created_bookings),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    if total_paid > total_remaining:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"إجمالي المدفوع ({total_paid}) يتجاوز إجمالي المتبقي بعد الرصيد الدائن ({total_remaining})",
        )

    # 3. If total_paid > 0, issue ONE single Receipt Voucher (RC) distributed across remaining_amount
    rc_ref = None
    if total_paid > Decimal("0.00"):
        pm_val = data.payment_method or PaymentMethod.CASH
        ref_doc = (data.reference_number or "").strip() or None
        active_shift = (
            await get_active_shift(db, current_user.id, raise_if_none=False)
            if pm_val == PaymentMethod.CASH
            else None
        )
        channel_acc = await get_payment_channel_account(db, pm_val, curr_str)
        rc_ref = await get_next_reference_number(db, "RC")

        primary_cust = await db.get(Customer, created_bookings[0].customer_id)
        ticket_list_str = "، ".join(b.ticket_number for b in created_bookings)

        # Equal distribution capped at each booking's remaining_amount; redistribute any leftover
        rem_caps = [Decimal(str(b.remaining_amount)).quantize(Decimal("0.01")) for b in created_bookings]
        base_share = (total_paid / Decimal(n_seats)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        shares: List[Decimal] = [Decimal("0.00")] * n_seats
        unassigned = total_paid
        for idx in range(n_seats):
            ideal = base_share if idx < n_seats - 1 else unassigned
            take = min(ideal, rem_caps[idx], unassigned)
            shares[idx] = take
            unassigned = (unassigned - take).quantize(Decimal("0.01"))
        if unassigned > Decimal("0.00"):
            for idx in range(n_seats):
                room = (rem_caps[idx] - shares[idx]).quantize(Decimal("0.01"))
                if room > Decimal("0.00"):
                    add_amt = min(room, unassigned)
                    shares[idx] = (shares[idx] + add_amt).quantize(Decimal("0.01"))
                    unassigned = (unassigned - add_amt).quantize(Decimal("0.01"))
                if unassigned == Decimal("0.00"):
                    break

        rc_tx = FinancialTransaction(
            transaction_id=rc_ref,
            type=TransactionType.PAYMENT_IN,
            entity_type=EntityType.CUSTOMER,
            entity_id=primary_cust.id,
            amount=total_paid,
            currency=curr_str,
            payment_method=pm_val,
            reference_number=ref_doc,
            notes=f"سند قبض موحد ({n_seats} مقاعد نقل بري: {ticket_list_str})",
            transaction_date=office_today(),
            booking_id=created_bookings[0].id,
            created_by=current_user.id,
            shift_id=active_shift.id if active_shift else None,
        )
        db.add(rc_tx)
        await db.flush()

        cust_acc_credits: Dict[int, Decimal] = {}
        for bk, share in zip(created_bookings, shares):
            if share <= Decimal("0.00"):
                continue
            alloc = VoucherAllocation(
                voucher_id=rc_tx.id,
                booking_id=bk.id,
                allocated_amount=share,
                target_currency=AccountCurrency(curr_str),
                exchange_rate=Decimal("1.000000"),
                allocated_in_booking_currency=share,
            )
            db.add(alloc)
            bk.paid_amount = (Decimal(str(bk.paid_amount)) + share).quantize(Decimal("0.01"))
            bk.remaining_amount = max(
                Decimal("0.00"),
                (Decimal(str(bk.selling_price)) - bk.paid_amount).quantize(Decimal("0.01")),
            )
            bk.status = (
                BookingStatus.CONFIRMED
                if bk.paid_amount > Decimal("0.00")
                else BookingStatus.PENDING
            )
            cust_acc_credits[bk.customer_id] = (
                cust_acc_credits.get(bk.customer_id, Decimal("0.00")) + share
            )

        je_lines = [{"account_id": channel_acc.id, "debit": total_paid, "credit": Decimal("0.0000")}]
        for cid, amt in cust_acc_credits.items():
            c_obj = await db.get(Customer, cid)
            c_acc = await get_entity_account(db, "customer", cid, curr_str, c_obj.name if c_obj else "")
            je_lines.append({"account_id": c_acc.id, "debit": Decimal("0.0000"), "credit": amt})

        rc_je_ref = await get_next_reference_number(db, "JE")
        await create_journal_entry(
            session=db,
            entry_number=rc_je_ref,
            reference_type="RECEIPT",
            reference_id=rc_ref,
            currency=curr_str,
            description=f"سند قبض موحد {rc_ref} لـ {n_seats} مقاعد نقل بري ({ticket_list_str})",
            lines_data=je_lines,
        )

        for cid in cust_acc_credits:
            c_obj = await db.get(Customer, cid)
            if c_obj:
                c_obj.balance = await get_entity_balance(db, "customer", cid)

    await db.commit()
    for bk in created_bookings:
        await db.refresh(bk)

    return {
        "count": len(created_bookings),
        "ticket_numbers": [b.ticket_number for b in created_bookings],
        "booking_ids": [b.id for b in created_bookings],
        "receipt_id": rc_ref,
        "total_paid": float(total_paid),
    }


@router.get("/unpaid")
async def get_unpaid_bookings(
    customer_id: int = Query(..., description="معرف العميل المطلوب جلب تذاكره المفتوحة"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    جلب التذاكر غير المسددة بالكامل لعميل محدد حصراً.
    يُستخدم في سند القبض لعزل التذاكر وتخصيص السداد.
    """
    stmt = (
        select(Booking)
        .where(
            Booking.customer_id == customer_id,
            Booking.remaining_amount > 0,
            Booking.status.in_(["confirmed", "pending"]),
        )
        .options(selectinload(Booking.customer))
        .order_by(Booking.booking_date)
    )
    res = await db.execute(stmt)
    bookings = res.scalars().all()

    return [
        {
            "id": b.id,
            "ticket_number": b.ticket_number,
            "type": b.type.value if hasattr(b.type, "value") else b.type,
            "selling_price": float(b.selling_price),
            "paid_amount": float(b.paid_amount),
            "remaining_amount": float(b.remaining_amount),
            "currency": b.currency or "YER",
        }
        for b in bookings
    ]


@router.get("/search", response_model=TicketSearchResponse)
async def search_tickets(
    q_name: Optional[str] = Query(None, description="Search by passenger name"),
    q_number: Optional[str] = Query(None, description="Search by phone or document number"),
    q_ticket: Optional[str] = Query(None, description="Search by ticket number"),
    booking_type: Optional[BookingType] = None,
    status: Optional[BookingStatus] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.employee),
            selectinload(Booking.supplier),
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.visa_details),
            selectinload(Booking.passport_details),
            selectinload(Booking.parcel_details),
        )
        .order_by(desc(Booking.created_at))
    )

    # If no search criteria provided, return empty list per requirement
    if not any([q_name, q_number, q_ticket, booking_type, status]):
        return TicketSearchResponse(items=[], total=0, page=page, limit=limit)

    # We must outerjoin all detail tables so that WHERE clauses can filter on them
    stmt = (
        stmt.outerjoin(Booking.customer)
        .outerjoin(Booking.flight_details)
        .outerjoin(Booking.transport_details)
        .outerjoin(Booking.visa_details)
        .outerjoin(Booking.passport_details)
        .outerjoin(Booking.parcel_details)
    )

    # Employee privacy restriction
    if current_user.role == UserRole.EMPLOYEE:
        stmt = stmt.where(Booking.employee_id == current_user.id)

    if booking_type:
        stmt = stmt.where(Booking.type == booking_type)
    if status:
        stmt = stmt.where(Booking.status == status)

    if q_name and q_name.strip():
        term = f"%{q_name.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(term),
                FlightBookingDetail.passenger_name.ilike(term),
                TransportBookingDetail.passenger_name.ilike(term),
                VisaBookingDetail.applicant_name.ilike(term),
                PassportBookingDetail.applicant_name.ilike(term),
                ParcelBookingDetail.sender_name.ilike(term),
                ParcelBookingDetail.receiver_name.ilike(term),
            )
        )
    if q_number and q_number.strip():
        term = f"%{q_number.strip()}%"
        stmt = stmt.where(
            or_(
                Customer.phone_number.ilike(term),
                Customer.passport_number.ilike(term),
                Customer.id_number.ilike(term),
                FlightBookingDetail.passport_number.ilike(term),
                FlightBookingDetail.passenger_phone.ilike(term),
                TransportBookingDetail.id_number.ilike(term),
                TransportBookingDetail.passenger_phone.ilike(term),
                VisaBookingDetail.passport_number.ilike(term),
                PassportBookingDetail.id_number.ilike(term),
            )
        )
    if q_ticket and q_ticket.strip():
        term = f"%{q_ticket.strip()}%"
        stmt = stmt.where(
            or_(
                Booking.ticket_number.ilike(term),
                Booking.booking_id.ilike(term),
            )
        )

    offset = (page - 1) * limit
    res = await db.execute(stmt.offset(offset).limit(limit))
    bookings = res.scalars().unique().all()

    items: List[TicketSearchItem] = []
    for b in bookings:
        pass_name = b.customer.name if b.customer else "عميل"
        pass_phone = b.customer.phone_number if b.customer else "--"
        doc_num = (b.customer.passport_number or b.customer.id_number) if b.customer else None
        comp_name = b.supplier.name if b.supplier else ""
        route = "--"
        tr_date = None
        tr_time = None

        if b.type == BookingType.FLIGHT and b.flight_details:
            pass_name = b.flight_details.passenger_name
            pass_phone = b.flight_details.passenger_phone
            doc_num = b.flight_details.passport_number
            comp_name = b.flight_details.airline_company or comp_name
            route = f"{b.flight_details.departure_airport} -> {b.flight_details.arrival_airport}"
            tr_date = b.flight_details.departure_date
            tr_time = b.flight_details.departure_time
        elif b.type == BookingType.TRANSPORT and b.transport_details:
            pass_name = b.transport_details.passenger_name
            pass_phone = b.transport_details.passenger_phone
            doc_num = b.transport_details.id_number
            comp_name = b.transport_details.transport_company or comp_name
            route = f"{b.transport_details.departure_station} -> {b.transport_details.arrival_station}"
            tr_date = b.transport_details.travel_date
            tr_time = b.transport_details.travel_time
        elif b.type == BookingType.VISA and b.visa_details:
            pass_name = b.visa_details.applicant_name
            pass_phone = b.visa_details.applicant_phone
            doc_num = b.visa_details.passport_number
            comp_name = f"تأشيرة {b.visa_details.visa_type}"
            route = f"تأشيرة {b.visa_details.visa_type}"
            tr_date = b.visa_details.application_date
        elif b.type == BookingType.PASSPORT and b.passport_details:
            pass_name = b.passport_details.applicant_name
            pass_phone = b.passport_details.applicant_phone
            doc_num = b.passport_details.id_number
            comp_name = f"جواز {b.passport_details.passport_type.value}"
            route = f"معاملة جواز ({b.passport_details.passport_type.value})"
            tr_date = b.passport_details.application_date
        elif b.type == BookingType.PARCEL and b.parcel_details:
            pass_name = b.parcel_details.sender_name
            pass_phone = b.parcel_details.sender_phone
            comp_name = b.parcel_details.parcel_type
            route = f"إلى: {b.parcel_details.delivery_destination}"
            tr_date = b.parcel_details.shipping_date

        cust_bal = await get_entity_balance(db, "customer", b.customer_id, b.currency) if b.customer_id else None

        items.append(
            TicketSearchItem(
                id=b.id,
                booking_id=b.booking_id,
                ticket_number=b.ticket_number,
                passenger_name=pass_name,
                passenger_phone=pass_phone,
                identity_number=doc_num,
                type=b.type,
                company_name=comp_name or "عالم النقل",
                booking_date=b.booking_date,
                route=route,
                travel_date=tr_date,
                travel_time=tr_time,
                employee_id=b.employee_id,
                employee_name=b.employee.full_name if b.employee else "مدير النظام",
                status=b.status,
                selling_price=b.selling_price,
                paid_amount=b.paid_amount,
                remaining_amount=b.remaining_amount,
                currency=b.currency,
                customer_id=b.customer_id,
                customer_balance=cust_bal,
                notes=b.notes,
            )
        )

    return TicketSearchResponse(
        items=items,
        total=len(items),
        page=page,
        limit=limit,
    )


@router.get("/")
async def list_bookings(
    booking_type: Optional[BookingType] = None,
    status_filter: Optional[BookingStatus] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.employee),
            selectinload(Booking.supplier),
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.visa_details),
            selectinload(Booking.passport_details),
            selectinload(Booking.parcel_details),
        )
        .order_by(desc(Booking.created_at))
    )

    # Strict role enforcement: Employee sees ONLY their own bookings
    if current_user.role == UserRole.EMPLOYEE:
        stmt = stmt.where(Booking.employee_id == current_user.id)

    if booking_type:
        stmt = stmt.where(Booking.type == booking_type)
    if status_filter:
        stmt = stmt.where(Booking.status == status_filter)

    if search:
        search_term = f"%{search}%"
        stmt = stmt.join(Booking.customer).where(
            (Booking.ticket_number.ilike(search_term))
            | (Booking.booking_id.ilike(search_term))
            | (Customer.name.ilike(search_term))
            | (Customer.phone_number.ilike(search_term))
        )

    stmt = stmt.offset(offset).limit(limit)
    res = await db.execute(stmt)
    bookings = res.scalars().all()

    return [format_booking_response(b, current_user.role) for b in bookings]


@router.get("/{id}")
async def get_booking(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .where(Booking.id == id)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.employee),
            selectinload(Booking.supplier),
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.visa_details),
            selectinload(Booking.passport_details),
            selectinload(Booking.parcel_details),
        )
    )
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض هذا الحجز")

    return format_booking_response(booking, current_user.role)


@router.get("/{id}/journal")
async def get_booking_journal_entries(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Booking).where(Booking.id == id).options(selectinload(Booking.customer))
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض قيود هذا الحجز")

    cust_bal = (
        await get_entity_balance(db, "customer", booking.customer_id, booking.currency)
        if booking.customer_id
        else None
    )

    ref_ids = [booking.ticket_number, booking.booking_id]
    je_stmt = (
        select(JournalEntry)
        .where(JournalEntry.reference_id.in_(ref_ids))
        .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
        .order_by(JournalEntry.date)
    )
    je_res = await db.execute(je_stmt)
    entries = je_res.scalars().all()

    entries_data = []
    for je in entries:
        lines = []
        for line in je.lines:
            lines.append({
                "id": line.id,
                "account_code": line.account.code if line.account else "",
                "account_name": line.account.name if line.account else "",
                "account_type": line.account.account_type.value if line.account else "",
                "debit": float(line.debit),
                "credit": float(line.credit),
                "debit_base": float(line.debit_base),
                "credit_base": float(line.credit_base),
            })
        entries_data.append({
            "id": je.id,
            "entry_number": je.entry_number,
            "date": je.date.isoformat(),
            "reference_type": je.reference_type,
            "reference_id": je.reference_id,
            "currency": je.currency.value,
            "description": je.description,
            "lines": lines,
        })

    return {
        "booking_id": booking.id,
        "ticket_number": booking.ticket_number,
        "customer_name": booking.customer.name if booking.customer else None,
        "customer_balance": float(cust_bal) if cust_bal is not None else None,
        "currency": booking.currency,
        "journal_entries": entries_data,
    }


@router.post("/{id}/cancel")
async def cancel_booking(
    id: int,
    data: BookingCancelRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.ACCOUNTANT:
        raise HTTPException(status_code=403, detail="المحاسب لا يملك صلاحية إلغاء الحجوزات")

    stmt = select(Booking).where(Booking.id == id).options(selectinload(Booking.customer))
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا يمكنك إلغاء حجز تابع لموظف آخر")
    check_employee_24h_window(booking, current_user, "إلغاء")

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="الحجز ملغي مسبقاً")

    credit_applied_amt = Decimal(str(getattr(booking, "credit_applied", None) or 0)).quantize(Decimal("0.01"))
    cash_paid_amt = max(
        Decimal("0.00"),
        (Decimal(str(booking.paid_amount)) - credit_applied_amt).quantize(Decimal("0.01")),
    )

    if data.refund_amount > cash_paid_amt:
        raise HTTPException(
            status_code=400,
            detail=f"المبلغ المسترد نقداً ({data.refund_amount}) لا يمكن أن يتجاوز المبلغ المدفوع نقداً ({cash_paid_amt})",
        )

    now = datetime.now(timezone.utc)
    old_data = {"status": booking.status.value, "paid": float(booking.paid_amount)}
    orig_remaining = Decimal(str(booking.remaining_amount)).quantize(Decimal("0.01"))

    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now
    booking.cancelled_by = current_user.id
    booking.cancellation_reason = data.reason
    booking.refund_amount = data.refund_amount
    booking.remaining_amount = Decimal("0.00")

    customer = booking.customer

    # Double-Entry Reverse Accounting for Cancellation
    curr_str = booking.currency or "YER"
    je_cancel_ref = await get_next_reference_number(db, "JE")

    cash_acc = await get_payment_channel_account(db, data.payment_method, curr_str)
    cust_acc = await get_entity_account(db, "customer", customer.id, curr_str, customer.name if customer else "")
    sales_acc = await get_account_by_code(db, f"4101-{curr_str}")
    cancel_fee_acc = await get_account_by_code(db, f"4201-{curr_str}")

    cancel_lines = [
        # Debit Sales Revenue to reverse the initial sale
        {"account_id": sales_acc.id, "debit": booking.selling_price, "credit": Decimal("0.0000")},
    ]

    # Credit Customer AR for remaining debt being cancelled PLUS any credit_applied consumed at booking creation
    cust_credit_reversal = (orig_remaining + credit_applied_amt).quantize(Decimal("0.01"))
    if cust_credit_reversal > Decimal("0.00"):
        cancel_lines.append(
            {"account_id": cust_acc.id, "debit": Decimal("0.0000"), "credit": cust_credit_reversal}
        )

    # Credit Cash for the refund paid back to the customer
    if data.refund_amount > 0:
        cancel_lines.append(
            {"account_id": cash_acc.id, "debit": Decimal("0.0000"), "credit": data.refund_amount}
        )

    # The office retains penalty from the cash portion = cash_paid_amt - refund_amount -> Credit Cancellation Fee Revenue
    retained_penalty = (cash_paid_amt - Decimal(str(data.refund_amount))).quantize(Decimal("0.01"))
    if retained_penalty > Decimal("0.00"):
        cancel_lines.append(
            {"account_id": cancel_fee_acc.id, "debit": Decimal("0.0000"), "credit": retained_penalty}
        )

    # Reverse Supplier AP and Cost of Sales if booking had cost
    if booking.cost_price > 0 and booking.supplier_id:
        cogs_acc = await get_account_by_code(db, f"5101-{curr_str}")
        supp_acc = await get_entity_account(db, "supplier", booking.supplier_id, curr_str)
        cancel_lines.append(
            {"account_id": supp_acc.id, "debit": booking.cost_price, "credit": Decimal("0.0000")}
        )
        cancel_lines.append(
            {"account_id": cogs_acc.id, "debit": Decimal("0.0000"), "credit": booking.cost_price}
        )

    await create_journal_entry(
        session=db,
        entry_number=je_cancel_ref,
        reference_type="CANCEL",
        reference_id=booking.ticket_number,
        currency=curr_str,
        description=f"قيد إلغاء الحجز {booking.ticket_number} - المسترد: {data.refund_amount} {curr_str} - السبب: {data.reason}",
        lines_data=cancel_lines,
    )

    if customer:
        customer.balance = await get_entity_balance(db, "customer", customer.id)
    if booking.supplier_id:
        supp_obj = await db.get(Supplier, booking.supplier_id)
        if supp_obj:
            supp_obj.balance = await get_entity_balance(db, "supplier", supp_obj.id)

    # If money is refunded back to customer, record payment_out and link to active shift (cash only)
    if data.refund_amount > 0 and customer:
        active_shift = (
            await get_active_shift(db, current_user.id, raise_if_none=False)
            if data.payment_method == PaymentMethod.CASH
            else None
        )
        py_ref = await get_next_reference_number(db, "PY")
        refund_record = FinancialTransaction(
            transaction_id=py_ref,
            type=TransactionType.PAYMENT_OUT,
            entity_type=EntityType.CUSTOMER,
            entity_id=customer.id,
            amount=data.refund_amount,
            currency=booking.currency,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            notes=f"مبلغ مسترد لإلغاء الحجز {booking.ticket_number}: {data.reason}",
            transaction_date=office_today(),
            booking_id=booking.id,
            created_by=current_user.id,
            shift_id=active_shift.id if active_shift else None,
        )
        db.add(refund_record)

    await log_audit_event(
        db,
        "UPDATE",
        "bookings",
        user=current_user,
        record_id=booking.id,
        old_data=old_data,
        new_data={"status": "cancelled", "refund_amount": float(data.refund_amount)},
        request=request,
    )

    await db.commit()
    return {"message": "تم إلغاء الحجز وتحديث الأثر المالي بنجاح"}


@router.post("/{id}/postpone")
async def postpone_booking(
    id: int,
    data: BookingPostponeRequest,
    request: Request,
    current_user: User = Depends(require_booking_role),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .where(Booking.id == id)
        .options(
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.customer),
            selectinload(Booking.employee),
        )
    )
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا يمكنك تعديل حجز تابع لموظف آخر")
    check_employee_24h_window(booking, current_user, "تأجيل")

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="لا يمكن تأجيل حجز ملغي")

    target_date = data.new_departure_date or data.new_travel_date
    if not target_date:
        raise HTTPException(status_code=400, detail="تاريخ السفر الجديد مطلوب")
    target_time = data.new_departure_time or data.new_travel_time

    old_date = ""
    if booking.type == BookingType.FLIGHT and booking.flight_details:
        old_date = f"{booking.flight_details.departure_date} {booking.flight_details.departure_time}"
        booking.flight_details.departure_date = target_date
        if target_time:
            booking.flight_details.departure_time = target_time
    elif booking.type == BookingType.TRANSPORT and booking.transport_details:
        old_date = f"{booking.transport_details.travel_date} {booking.transport_details.travel_time}"
        booking.transport_details.travel_date = target_date
        if target_time:
            booking.transport_details.travel_time = target_time
    else:
        booking.booking_date = datetime.combine(
            target_date, target_time or datetime.min.time(), tzinfo=timezone.utc
        )

    if data.reason:
        booking.notes = (booking.notes + " | " if booking.notes else "") + f"تأجيل الرحلة: {data.reason}"

    await log_audit_event(
        db,
        "UPDATE",
        "bookings",
        user=current_user,
        record_id=booking.id,
        new_data={
            "action": "postpone",
            "old_date": old_date,
            "new_date": str(data.new_departure_date),
            "reason": data.reason,
        },
        request=request,
    )
    await db.commit()
    return {"message": "تم تأجيل موعد الرحلة بنجاح", "new_date": str(data.new_departure_date)}


@router.post("/{id}/reroute")
async def reroute_booking(
    id: int,
    data: BookingRerouteRequest,
    request: Request,
    current_user: User = Depends(require_booking_role),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .where(Booking.id == id)
        .options(
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.parcel_details),
            selectinload(Booking.customer),
            selectinload(Booking.employee),
        )
    )
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا يمكنك تعديل حجز تابع لموظف آخر")
    check_employee_24h_window(booking, current_user, "تغيير مسار")

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="لا يمكن تغيير مسار حجز ملغي")

    old_route = ""
    new_route = data.new_destination
    if booking.type == BookingType.FLIGHT and booking.flight_details:
        old_route = f"{booking.flight_details.departure_airport} -> {booking.flight_details.arrival_airport}"
        booking.flight_details.arrival_airport = data.new_destination
        if data.new_departure_station:
            booking.flight_details.departure_airport = data.new_departure_station
        new_route = f"{booking.flight_details.departure_airport} -> {booking.flight_details.arrival_airport}"
    elif booking.type == BookingType.TRANSPORT and booking.transport_details:
        old_route = f"{booking.transport_details.departure_station} -> {booking.transport_details.arrival_station}"
        booking.transport_details.arrival_station = data.new_destination
        if data.new_departure_station:
            booking.transport_details.departure_station = data.new_departure_station
        new_route = f"{booking.transport_details.departure_station} -> {booking.transport_details.arrival_station}"
    elif booking.type == BookingType.PARCEL and booking.parcel_details:
        old_route = booking.parcel_details.delivery_destination
        booking.parcel_details.delivery_destination = data.new_destination

    # Handle financial price difference with Double-Entry Journal Entry
    diff_val = Decimal(str(data.price_difference))
    if diff_val != Decimal("0.00"):
        curr_str = booking.currency or "YER"
        booking.selling_price += diff_val
        booking.remaining_amount += diff_val

        je_ref = await get_next_reference_number(db, "JE")
        cust_acc = await get_entity_account(
            db, "customer", booking.customer_id, curr_str, booking.customer.name if booking.customer else ""
        )
        sales_acc = await get_account_by_code(db, f"4101-{curr_str}")

        if diff_val > 0:
            # Customer pays extra: Debit Customer AR, Credit Sales Revenue
            adj_lines = [
                {"account_id": cust_acc.id, "debit": diff_val, "credit": Decimal("0.0000")},
                {"account_id": sales_acc.id, "debit": Decimal("0.0000"), "credit": diff_val},
            ]
        else:
            # Price reduction: Debit Sales Revenue, Credit Customer AR
            abs_diff = abs(diff_val)
            adj_lines = [
                {"account_id": sales_acc.id, "debit": abs_diff, "credit": Decimal("0.0000")},
                {"account_id": cust_acc.id, "debit": Decimal("0.0000"), "credit": abs_diff},
            ]

        await create_journal_entry(
            session=db,
            entry_number=je_ref,
            reference_type="REROUTE",
            reference_id=booking.ticket_number,
            currency=curr_str,
            description=f"قيد تسوية تغيير مسار الحجز {booking.ticket_number} - فارق السعر: {diff_val} {curr_str}",
            lines_data=adj_lines,
        )
        if booking.customer:
            booking.customer.balance = await get_entity_balance(db, "customer", booking.customer.id)

    if data.reason:
        booking.notes = (booking.notes + " | " if booking.notes else "") + f"تغيير المسار: {data.reason}"

    await log_audit_event(
        db,
        "UPDATE",
        "bookings",
        user=current_user,
        record_id=booking.id,
        new_data={
            "action": "reroute",
            "old_route": old_route,
            "new_route": new_route,
            "price_difference": float(diff_val),
            "reason": data.reason,
        },
        request=request,
    )
    await db.commit()
    return {"message": "تم تغيير مسار الرحلة وتحديث الأثر المالي بنجاح", "new_route": new_route}


@router.get("/{id}/print")
async def print_booking(
    id: int,
    mode: str = Query("thermal", pattern="^(thermal|a4)$"),
    format: str = Query("html", pattern="^(html|pdf)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Booking)
        .where(Booking.id == id)
        .options(
            selectinload(Booking.customer),
            selectinload(Booking.employee),
            selectinload(Booking.supplier),
            selectinload(Booking.flight_details),
            selectinload(Booking.transport_details),
            selectinload(Booking.visa_details),
            selectinload(Booking.passport_details),
            selectinload(Booking.parcel_details),
        )
    )
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    if current_user.role == UserRole.EMPLOYEE and booking.employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="لا يمكنك طباعة حجز تابع لموظف آخر")

    # Fetch settings
    s_res = await db.execute(select(Settings).limit(1))
    office_settings = s_res.scalar_one_or_none()
    if not office_settings:
        office_settings = Settings()

    if format == "pdf":
        from app.services.print_service import WEASYPRINT_AVAILABLE
        if WEASYPRINT_AVAILABLE:
            pdf_data = generate_voucher_pdf(booking, office_settings, mode=mode)
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename=voucher-{booking.ticket_number}.pdf"},
            )
        html_print = generate_voucher_html(booking, office_settings, mode=mode).replace(
            "<body>", '<body onload="window.print()">'
        )
        return Response(content=html_print, media_type="text/html; charset=utf-8")

    # Default HTML
    html_content = generate_voucher_html(booking, office_settings, mode=mode)
    return Response(content=html_content, media_type="text/html")
