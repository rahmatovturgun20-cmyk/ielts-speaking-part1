# Multilevel Mock Test — VPS Deploy Qo'llanmasi

## IP: 189.74.96.164
## Domen: multilevelmocktest.uz

---

## 1. DNS sozlash (avval buni qiling)

Domen sotib olgan provayderingiz panelida (registon.uz yoki boshqa):

```
A record:  multilevelmocktest.uz  ->  189.74.96.164
A record:  www.multilevelmocktest.uz  ->  189.74.96.164
```

**Eslatma:** DNS 10 daqiqadan 24 soatgacha yangilanadi.

---

## 2. VPS ga ulanish (SSH)

Windows PowerShell da:

```powershell
ssh root@189.74.96.164
```

Parolni kiriting (VPS panelida ko'rsatilgan bo'ladi).

---

## 3. Fayllarni VPS ga yuklash

### 3-usul: Git orqali (tavsiya etiladi)

VPS ichida:

```bash
# Git o'rnatish
apt-get install -y git

# Loyhani GitHub dan olish (avval GitHub ga yuklab qo'ying)
cd /var/www
git clone https://github.com/USERNAME/mocktest.git mocktest
```

### B-usul: SCP orqali (to'g'ridan-to'g'ri)

Windows PowerShell da (loyha papkasida):

```powershell
# 1. VPS da papka yaratish
ssh root@189.74.96.164 "mkdir -p /var/www/mocktest"

# 2. Fayllarni yuklash (loyha papkasida bo'ling)
scp -r ./* root@189.74.96.164:/var/www/mocktest/
```

**Muhim:** `site.db`, `config.json`, `receipts/`, `*.pem`, `*.key`, `*.log` yuklanmaydi (gitignore da).

---

## 4. VPS da o'rnatish

```bash
cd /var/www/mocktest
sudo bash deploy/deploy.sh
```

Bu skript hammasini qiladi:
- Python, nginx, certbot o'rnatadi
- venv yaratadi va requirements.txt o'rnatadi
- systemd xizmati (avtomatik ishga tushish)
- nginx reverse proxy
- Let's Encrypt SSL (bepul sertifikat)

---

## 5. config.json yaratish (VPS da)

```bash
cd /var/www/mocktest
nano config.json
```

Quyidagilarni yozing (o'zingizning ma'lumotlaringiz bilan):

```json
{
  "secret_key": "ozi-avtomatik-yaratiladi",
  "admin_phone": "+998998941028",
  "admin_password": "7tpUCf1ZF9LU8w",
  "card_number": "KARTA_RAQAMI",
  "card_holder": "KARTA_EGASI_FISH",
  "base_url": "https://multilevelmocktest.uz"
}
```

`Ctrl+X` → `Y` → `Enter` bilan saqlang.

---

## 6. Admin yaratish

```bash
cd /var/www/mocktest
venv/bin/python app.py create-admin +998998941028 7tpUCf1ZF9LU8w
```

---

## 7. Tekshirish

```bash
systemctl status mocktest        # ishga tushganini ko'rish
systemctl restart mocktest       # qayta ishga tushirish
journalctl -u mocktest -f        # loglarni kuzatish
```

Sayt: https://multilevelmocktest.uz
Admin: https://multilevelmocktest.uz/admin

---

## 8. Yangilanish yuborish (har safar o'zgartirish kiritganda)

```bash
cd /var/www/mocktest
git pull                        # (git ishlatilsa)
sudo systemctl restart mocktest
```
