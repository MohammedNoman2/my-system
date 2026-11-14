export type UserRole = 'admin' | 'employee' | 'accountant';

export interface User {
  id: number;
  username: string;
  full_name: string;
  email?: string;
  phone_number?: string;
  role: UserRole;
  is_active: boolean;
  created_at?: string;
}

export type BookingType = 'flight' | 'transport' | 'visa' | 'passport' | 'parcel';

export type BookingStatus = 'pending' | 'confirmed' | 'cancelled';

export interface FlightBookingDetail {
  airline_company: string;
  flight_number: string;
  departure_airport: string;
  arrival_airport: string;
  departure_date: string;
  departure_time: string;
  return_date?: string | null;
  return_time?: string | null;
  ticket_type: 'oneway' | 'roundtrip';
  allowed_weight?: number | null;
  passenger_name: string;
  passenger_phone: string;
  passport_number: string;
  birth_date: string;
  birth_place: string;
  passport_image_url?: string | null;
}

export interface TransportBookingDetail {
  transport_company: string;
  departure_station: string;
  arrival_station: string;
  travel_date: string;
  travel_time: string;
  passenger_name: string;
  passenger_phone: string;
  id_number: string;
  birth_date: string;
  birth_place: string;
  id_image_url?: string | null;
}

export interface VisaBookingDetail {
  visa_type: string;
  application_date: string;
  applicant_name: string;
  applicant_phone: string;
  passport_number: string;
  birth_date: string;
  birth_place: string;
  passport_image_url?: string | null;
}

export interface PassportBookingDetail {
  passport_type: 'new' | 'renewal' | 'lost' | 'damaged';
  priority: 'normal' | 'urgent';
  application_date: string;
  expected_delivery_date?: string | null;
  applicant_name: string;
  applicant_phone: string;
  id_number: string;
  birth_date: string;
  birth_place: string;
  id_image_url?: string | null;
}

export interface ParcelBookingDetail {
  sender_name: string;
  sender_phone: string;
  receiver_name: string;
  receiver_phone: string;
  delivery_destination: string;
  parcel_type: string;
  weight: number;
  content_description?: string | null;
  shipping_date: string;
}

export interface Customer {
  id: number;
  name: string;
  phone_number: string;
  email?: string | null;
  address?: string | null;
  passport_number?: string | null;
  id_number?: string | null;
  nationality?: string | null;
  notes?: string | null;
  balance: number;
  credit_balances?: Record<string, number>;
  created_at?: string;
}

export interface Supplier {
  id: number;
  name: string;
  phone_number?: string | null;
  service_type?: string | null;
  address?: string | null;
  balance: number;
  is_active: boolean;
  created_at?: string;
}

export interface Booking {
  id: number;
  booking_id: string;
  ticket_number: string;
  type: BookingType;
  customer_id: number;
  employee_id: number;
  created_by_id?: number;
  created_by_name?: string;
  cost_price?: number; // Omitted for employee role
  selling_price: number;
  paid_amount: number;
  credit_applied?: number;
  remaining_amount: number;
  currency: string;
  supplier_id?: number | null;
  notes?: string | null;
  status: BookingStatus;
  booking_date: string;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  refund_amount?: number;
  customer?: Customer;
  employee?: User;
  supplier?: Supplier;
  flight_details?: FlightBookingDetail;
  transport_details?: TransportBookingDetail;
  visa_details?: VisaBookingDetail;
  passport_details?: PassportBookingDetail;
  parcel_details?: ParcelBookingDetail;
}

export interface TicketSearchItem {
  id: number;
  booking_id: string;
  ticket_number: string;
  passenger_name: string;
  passenger_phone: string;
  identity_number?: string | null;
  type: BookingType;
  company_name: string;
  booking_date: string;
  route: string;
  travel_date?: string | null;
  travel_time?: string | null;
  employee_id: number;
  employee_name: string;
  status: BookingStatus;
  selling_price: number;
  paid_amount: number;
  remaining_amount: number;
  currency: string;
  customer_id: number;
  customer_balance?: number | null;
  notes?: string | null;
}

export interface TicketSearchResponse {
  items: TicketSearchItem[];
  total: number;
  page: number;
  limit: number;
}

export interface OfficeSettings {
  office_name: string;
  tagline: string;
  address: string;
  phone_numbers: string;
  email: string;
  website: string;
  default_currency: string;
  footer_text: string;
  logo_image_url?: string | null;
  logo_data?: string | null;
}

export interface ExchangeRate {
  id: number;
  from_currency: string;
  to_currency: string;
  rate: number;
  updated_at?: string;
}

export type TransactionType = 'payment_in' | 'payment_out' | 'expense' | 'refund';

export interface FinancialTransaction {
  id: number;
  transaction_id: string;
  type: TransactionType;
  amount: number;
  currency: string;
  entity_type: 'customer' | 'supplier' | 'office' | 'none';
  entity_id?: number | null;
  entity_name?: string | null;
  customer_id?: number | null;
  supplier_id?: number | null;
  booking_id?: number | null;
  payment_method: 'cash' | 'bank_transfer' | 'check' | 'cheque' | 'credit';
  reference_document?: string | null;
  reference_number?: string | null;
  expense_type?: string | null;
  notes?: string | null;
  transaction_date: string;
  is_void?: boolean;
  voided_at?: string | null;
  void_reason?: string | null;
  reversal_je_number?: string | null;
  shift_id?: number | null;
  created_by?: number;
  customer?: Customer;
  supplier?: Supplier;
}

export interface ReportFilter {
  report_type: 'bookings_detailed' | 'revenue' | 'expenses' | 'profit_loss' | 'debts' | 'employee_performance' | 'cash_flow';
  start_date?: string;
  end_date?: string;
  service_type?: BookingType;
  employee_id?: number;
  customer_id?: number;
  supplier_id?: number;
}

export interface ReportSummary {
  title: string;
  report_type: string;
  period: string;
  total_count: number;
  total_amount: number;
  totals_by_currency?: Record<string, any>;
  additional_totals?: Record<string, any>;
  rows: Array<Record<string, any>>;
}

export interface DashboardStats {
  today_sales: number;
  monthly_sales: number;
  monthly_expenses: number;
  total_bookings_month: number;
  new_customers_month: number;
  alerts: {
    debts_over_30_days: number;
    passports_expiring_3_months: number;
  };
  charts: {
    monthly_trend: Array<{ month: string; sales: number; expenses: number }>;
    bookings_by_type: Array<{ type: string; count: number }>;
  };
}
