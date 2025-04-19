import psutil
import platform
import time
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from telegram import Update, InputFile
from telegram.ext import ContextTypes

# Пользователи с доступом к !status
ALLOWED_USER_IDS = [5403794760, 5742749531]

# Пользователи с доступом к !debug-all
SUPER_ADMIN_IDS = [5403794760, 5742749531]

# Время запуска бота
start_time = time.time()


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ Вы не являетесь Администратором этого Бота ⛔")
        return

    uptime = timedelta(seconds=int(time.time() - start_time))
    boot_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_cores = psutil.cpu_percent(interval=1, percpu=True)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    system = platform.system()
    machine = platform.machine()

    text = (
        f"🖥️ <b>Статус системы:</b>\n"
        f"🔧 OS: <b>{system}</b> ({machine})\n"
        f"⏱ Аптайм: <code>{uptime}</code>\n"
        f"📆 Запущен: <code>{boot_time}</code>\n"
        f"📊 CPU: <b>{cpu_percent}%</b>\n"
        f"📦 RAM: <b>{ram.percent}%</b> из {round(ram.total / 1024**3, 1)} GB\n"
        f"💽 Диск: <b>{disk.percent}%</b> из {round(disk.total / 1024**3, 1)} GB"
    )

    await update.message.reply_text(text, parse_mode="HTML")

    # CPU график
    plt.figure(figsize=(9, 4))
    plt.bar(range(len(cpu_cores)), cpu_cores)
    plt.title("Загрузка CPU по ядрам")
    plt.xlabel("Ядро")
    plt.ylabel("Загрузка (%)")
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    buffer.name = "cpu_status.png"
    plt.close()

    await update.message.reply_photo(photo=buffer, caption="📊 График загрузки CPU по ядрам")


async def debugall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in SUPER_ADMIN_IDS:
        await update.message.reply_text("🚫 Вы не являетесь Администратором этого Бота 🚫")
        return

    # Системные данные
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc).astimezone(timezone(timedelta(hours=2)))
    uptime = timedelta(seconds=int(time.time() - psutil.boot_time()))
    cpu_percent_total = psutil.cpu_percent()
    cpu_percent_cores = psutil.cpu_percent(percpu=True)
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)

    # Топ 5 по CPU
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    top_cpu = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    top_mem = sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:5]

    # CPU график
    plt.figure(figsize=(8, 4))
    plt.bar(range(len(cpu_percent_cores)), cpu_percent_cores)
    plt.xlabel('Ядро')
    plt.ylabel('Загрузка (%)')
    plt.title('Загрузка CPU по ядрам')
    plt.tight_layout()

    cpu_img = io.BytesIO()
    plt.savefig(cpu_img, format='png')
    cpu_img.seek(0)
    cpu_img.name = "cpu_debug.png"
    plt.close()

    # Формирование отчета
    used_gb = round(ram.used / 1024**3, 1)
    free_gb = round((ram.total - ram.used) / 1024**3, 1)
    text = (
        f"<b>🧠 Полный системный отчёт</b>\n\n"
        f"🖥 <b>OS:</b> {platform.system()} ({platform.machine()})\n"
        f"⏱ <b>Аптайм:</b> <code>{uptime}</code>\n"
        f"🚀 <b>Запущен:</b> {boot_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+2)\n"
        f"📊 <b>CPU:</b> {cpu_percent_total}% (ядер: {psutil.cpu_count(logical=True)})\n"
        f"📈 <b>Load Avg:</b> {load_avg}\n"
        f"💾 <b>RAM:</b> {ram.percent}% из {round(ram.total / 1024**3, 1)} GB\n"
        f"⏳ Используется: {used_gb} GB | Свободно: {free_gb} GB\n"
        f"📄 <b>SWAP:</b> {swap.percent}% из {round(swap.total / 1024**3, 1)} GB\n"
        f"🗂 <b>Диск:</b> {disk.percent}% из {round(disk.total / 1024**3, 1)} GB\n"
        f"🌐 <b>Сеть:</b> Отправлено: {round(net.bytes_sent / 1024**2, 1)} MB | Получено: {round(net.bytes_recv / 1024**2, 1)} MB\n\n"
        f"<b>🔥 Топ процессов по CPU:</b>\n"
    )
    for proc in top_cpu:
        text += f"🔹 {proc['name']} (PID {proc['pid']}): {proc['cpu_percent']}%\n"

    text += "\n<b>💾 Топ процессов по памяти:</b>\n"
    for proc in top_mem:
        text += f"🟦 {proc['name']} (PID {proc['pid']}): {proc['memory_percent']:.1f}%\n"

    await update.message.reply_text(text, parse_mode="HTML")
    await update.message.reply_photo(InputFile(cpu_img), caption="📊 График загрузки CPU по ядрам")