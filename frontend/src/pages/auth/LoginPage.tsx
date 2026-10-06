import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { LogIn, Lock, User as UserIcon, ShieldAlert } from 'lucide-react';
import { useAuthStore } from '../../context/authStore';
import { useUIStore } from '../../context/uiStore';
import api from '../../services/api';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';

const loginSchema = yup.object({
  username: yup.string().required('اسم المستخدم مطلوب'),
  password: yup.string().required('كلمة المرور مطلوبة'),
});

type LoginFormValues = yup.InferType<typeof loginSchema>;

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const addToast = useUIStore((state) => state.addToast);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [publicSettings, setPublicSettings] = useState<{
    office_name?: string;
    tagline?: string;
    logo_data?: string | null;
    logo_image_url?: string | null;
  } | null>(null);

  useEffect(() => {
    async function loadPublicSettings() {
      try {
        const res = await api.get('/settings/public');
        setPublicSettings(res.data);
      } catch (e) {
        // Fallback silently if offline or uninitialized
      }
    }
    loadPublicSettings();
  }, []);

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: yupResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await login(values.username, values.password);
      addToast('تم تسجيل الدخول بنجاح', 'success');
      navigate(from, { replace: true });
    } catch (err: any) {
      setErrorMessage(err.message || 'فشل تسجيل الدخول');
      addToast(err.message || 'فشل تسجيل الدخول', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const logoSrc = publicSettings?.logo_data || publicSettings?.logo_image_url;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-blue-50/40 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-[#1e3a8a] to-blue-600 text-white flex items-center justify-center font-black text-2xl shadow-xl shadow-blue-900/20 overflow-hidden border-2 border-white/80 p-1">
            {logoSrc ? (
              <img
                src={logoSrc}
                alt="شعار المكتب"
                className="w-full h-full object-contain rounded-xl bg-white/10"
              />
            ) : (
              <span>ARP</span>
            )}
          </div>
        </div>
        <h2 className="mt-4 text-center text-2xl font-black tracking-tight text-slate-900">
          {publicSettings?.office_name || 'منصة الحجوزات المتقدمة'}
        </h2>
        <p className="mt-1 text-center text-sm font-medium text-slate-500">
          {publicSettings?.tagline || 'عالم النقل للسفريات والسياحة والنقل البري'}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-100">
          {errorMessage && (
            <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3 text-red-700 text-sm">
              <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5 text-red-600" />
              <div className="flex-1 font-medium leading-relaxed">{errorMessage}</div>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <Input
              label="اسم المستخدم"
              placeholder="admin / employee / accountant"
              icon={<UserIcon className="w-4 h-4" />}
              error={errors.username?.message}
              {...register('username')}
            />

            <div>
              <Input
                label="كلمة المرور"
                type="password"
                placeholder="••••••••"
                icon={<Lock className="w-4 h-4" />}
                error={errors.password?.message}
                {...register('password')}
              />
              <div className="flex items-center justify-end mt-2">
                <Link
                  to="/forgot-password"
                  className="text-xs text-[#1e3a8a] hover:underline font-medium"
                >
                  نسيت كلمة المرور؟
                </Link>
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
              icon={<LogIn className="w-4 h-4" />}
              className="w-full shadow-md"
            >
              تسجيل الدخول
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
