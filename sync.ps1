# الانتقال إلى مجلد المشروع
Set-Location "C:\Users\Mohammed\Desktop\my-system"

# التحقق من وجود تعديلات جديدة لتجنب الأخطاء
$status = git status --porcelain
if ($status) {
    git add .
    git commit -m "feat: complete project sync with frontend, alembic migrations, and dev log"
    git push origin main
}