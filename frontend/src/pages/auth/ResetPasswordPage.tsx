import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Lock, CheckCircle2 } from 'lucide-react';
import api from '../../services/api';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { useUIStore } from '../../context/uiStore';

const resetSchema = yup.object({
  new_password: yup
    .string()
    .min(6, 'كلمة المرور يجب أن تكون 6 أحرف على الأقل')
    .required('كلمة المرور الجديدة مطلوبة'),
  confirm_password: yup
    .string()
    .oneOf([yup.ref('new_password')], 'كلمتا المرور غير متطابقتين')
    .required('تأكيد كلمة المرور مطلوب'),
});

type ResetFormValues = yup.InferType<typeof resetSchema>;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();
  const addToast = useUIStore((state) => state.addToast);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetFormValues>({
    resolver: yupResolver(resetSchema),
  });

  const onSubmit = async (values: ResetFormValues) => {
    if (!token) {
      setErrorMessage('رمز الاستعادة مفقود من الرابط');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      await api.post('/auth/reset-password', {
        token,
        new_password: values.new_password,
      });
      addToast('تم تغيير كلمة المرور بنجاح، يرجى تسجيل الدخول', 'success');
      navigate('/login');
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'فشل إعادة تعيين كلمة المرور');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-100">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-slate-900">تعيين كلمة مرور جديدة</h2>
            <p className="mt-1 text-sm text-slate-500">
              أدخل كلمة المرور الجديدة لحسابك لتسجيل الدخول.
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 text-xs rounded-lg font-medium">
              {errorMessage}
            </div>
          )}

          {!token ? (
            <div className="text-center text-red-600 text-sm py-4">
              رابط الاستعادة غير صالح أو يفتقد لرمز التحقق (token).
              <div className="mt-4">
                <Link to="/forgot-password" className="text-[#1e3a8a] font-bold underline">
                  طلب رابط استعادة جديد
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <Input
                label="كلمة المرور الجديدة"
                type="password"
                placeholder="••••••••"
                icon={<Lock className="w-4 h-4" />}
                error={errors.new_password?.message}
                {...register('new_password')}
              />

              <Input
                label="تأكيد كلمة المرور الجديدة"
                type="password"
                placeholder="••••••••"
                icon={<Lock className="w-4 h-4" />}
                error={errors.confirm_password?.message}
                {...register('confirm_password')}
              />

              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isLoading}
                className="w-full mt-2"
              >
                تحديث كلمة المرور
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
