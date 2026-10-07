# الانتقال إلى مجلد المشروع
cd "C:\Users\Mohammed\Desktop\my-system"

# التحقق من وجود تعديلات جديدة لتجنب الأخطاء
$status = git status --porcelain
if ($status) {
    git add .
    $date = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "Auto sync: $date"
    git push
}