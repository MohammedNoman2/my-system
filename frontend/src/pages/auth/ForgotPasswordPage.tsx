import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { Link } from 'react-router-dom';
import { Mail, ArrowRight, CheckCircle2 } from 'lucide-react';
import api from '../../services/api';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';

const forgotSchema = yup.object({
  email: yup.string().email('صيغة البريد الإلكتروني غير صحيحة').required('البريد الإلكتروني مطلوب'),
});

type ForgotFormValues = yup.InferType<typeof forgotSchema>;

export function ForgotPasswordPage() {
  const [isSuccess, setIsSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotFormValues>({
    resolver: yupResolver(forgotSchema),
  });

  const onSubmit = async (values: ForgotFormValues) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await api.post('/auth/forgot-password', { email: values.email });
      setIsSuccess(true);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'فشل إرسال طلب الاستعادة');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-100">
          <div className="text-center mb-6">
            <h2 className="text-xl font-bold text-slate-900">استعادة كلمة المرور</h2>
            <p className="mt-1 text-sm text-slate-500">
              أدخل بريدك الإلكتروني المسجل وسنرسل لك رابطاً لتعيين كلمة مرور جديدة.
            </p>
          </div>

          {isSuccess ? (
            <div className="text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <p className="text-sm font-medium text-slate-800">
                إذا كان البريد الإلكتروني مسجلاً لدينا، فقد تم إرسال تعليمات الاستعادة. يرجى مراجعة بريدك.
              </p>
              <div className="pt-4">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 text-sm text-[#1e3a8a] font-semibold hover:underline"
                >
                  <ArrowRight className="w-4 h-4" /> العودة لتسجيل الدخول
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {errorMessage && (
                <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg">
                  {errorMessage}
                </div>
              )}

              <Input
                label="البريد الإلكتروني"
                type="email"
                placeholder="example@alamalnaql.com"
                icon={<Mail className="w-4 h-4" />}
                error={errors.email?.message}
                {...register('email')}
              />

              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isLoading}
                className="w-full mt-2"
              >
                إرسال رابط الاستعادة
              </Button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800"
                >
                  <ArrowRight className="w-3.5 h-3.5" /> العودة لتسجيل الدخول
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
