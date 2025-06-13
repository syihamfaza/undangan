from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials


def run_checker(socketio, sheet_index=4, control=None):
    def emit_log(message):
        print("[LOG]",message)  # Log to console for debugging
        log.append(message)
        try:
            socketio.emit("checker_log", message)
        except Exception as emit_err:
            log.append(f"⚠️ Gagal mengirim log ke client: {emit_err}")

    control.get("stop_requested")

    log = []

    # Setup headless Chrome
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    key = "D:\\Code\\key.json"

    try:
        # Setup Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(key, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key("1J-Hu6RgyJgj_5TI0YzMEhNPFpwy8RiYHvTImtszzPb8")
        sheet = spreadsheet.get_worksheet(sheet_index)
        rows = sheet.get_all_records(expected_headers=["username", "password", "key", "pangkalan"])
    except Exception as sheet_err:
        emit_log(f"❌ Gagal mengakses Google Sheets: {sheet_err}")
        return log

    LOGIN_URL = "https://subsiditepatlpg.mypertamina.id/merchant-login"
    PRODUCT_URL = "https://subsiditepatlpg.mypertamina.id/merchant/app/manage-product"
    LOGOUT_URL = "https://subsiditepatlpg.mypertamina.id/merchant/app/profile-merchant"

    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 20)
    except Exception as driver_err:
        emit_log(f"❌ Gagal membuka Chrome WebDriver: {driver_err}")
        return log

    for idx, row in enumerate(rows, start=2):
        if any(not str(row.get(field)).strip() for field in ["username", "password", "key", "pangkalan"]):
            emit_log(f"⚠️ Melewati baris {idx} karena data tidak lengkap: {row}")
            continue
        if control and control.get("stop_requested"):
            emit_log("🛑 Dihentikan oleh pengguna.")
            break

        username = str(row['username']).zfill(12)
        password = str(row['password']).zfill(6)
        pangkalan = row['pangkalan']

        login_success = False
        max_try = 2
        attempt = 0

        while not login_success and attempt < max_try:
            try:
                attempt += 1
                emit_log(f"🔐 Login percobaan {attempt} untuk {username}")
                driver.get(LOGIN_URL)

                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Masukkan nomor ponsel atau 𝑒𝑚𝑎𝑖𝑙']"))).send_keys(username)
                wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Masukkan PIN Anda']"))).send_keys(password)
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Masuk']"))).click()
                time.sleep(2)

                try:
                    gagal_login = driver.find_element(By.XPATH, "//h5[text()='Gagal Masuk Akun']")
                    if gagal_login.is_displayed():
                        emit_log(f"❌ Login gagal: {username}. Menunggu 2 menit sebelum coba lagi.")
                        time.sleep(120)
                        continue
                except:
                    pass

                login_success = True
                emit_log(f"✅ Login berhasil untuk {username}")

                driver.get(PRODUCT_URL)
                time.sleep(3)

                stok_container = wait.until(EC.presence_of_element_located((By.XPATH,
                    "//div[contains(@class, 'styles_containerColumn') and span[text()='Stok LPG 3kg saat ini']]")))

                stok_teks = stok_container.find_elements(By.TAG_NAME, "span")[1].text
                stok_angka = int(''.join(filter(str.isdigit, stok_teks)))

                if stok_angka > 0:
                    msg = f"📦 Stok tersedia untuk {pangkalan} : {stok_angka} tabung"
                    sheet.update_cell(idx, 5, f"{stok_angka} tabung tersedia")
                else:
                    msg = f"⭕ Stok kosong untuk {pangkalan}"
                    sheet.update_cell(idx, 5, "Stok kosong")

                emit_log(msg)

                # Logout
                driver.get(LOGOUT_URL)
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Keluar Aplikasi']"))).click()
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Ya, Keluar Aplikasi']"))).click()
                emit_log(f"🚪 Logout selesai untuk {username}\n--------------------------")
                break

            except Exception as e:
                error_msg = f"⚠️ Gagal login atau proses untuk {username}: {e}"
                emit_log(error_msg)
                sheet.update_cell(idx, 5, "❌ Gagal login atau proses")
                continue

    driver.quit()
    emit_log("✔ Selesai cek semua akun.")
    return log