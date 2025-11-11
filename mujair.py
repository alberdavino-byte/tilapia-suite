import streamlit as st
import re
import os
import time
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ⭐ URL Configuration
def get_app_url():
    """Dapatkan URL aplikasi dengan prioritas: env > secrets > default"""
    url = os.getenv("APP_URL") or st.secrets.get("APP_URL", None)
    
    if url:
        return url.rstrip('/')
    
    # ⚠️ GANTI dengan URL Streamlit app Anda!
    return "https://tilapia-suite-rmjbydvuajkwqwfs.streamlit.app/"

# Inisialisasi Supabase
@st.cache_resource
def init_supabase() -> Client:
    """Inisialisasi koneksi ke Supabase"""
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    
    if not url or not key:
        st.error("❌ SUPABASE_URL dan SUPABASE_KEY harus diset!")
        st.info("Tambahkan di `.streamlit/secrets.toml` atau environment variables")
        st.stop()
    
    return create_client(url, key)

# Validasi Email
def validate_email(email: str) -> bool:
    """Validasi format email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# Validasi Password
def validate_password(password: str) -> tuple[bool, str]:
    """Validasi password dengan requirement ketat"""
    if len(password) < 8:
        return False, "Password minimal 8 karakter"
    if not re.search(r'[A-Z]', password):
        return False, "Harus ada huruf besar (A-Z)"
    if not re.search(r'[a-z]', password):
        return False, "Harus ada huruf kecil (a-z)"
    if not re.search(r'[0-9]', password):
        return False, "Harus ada angka (0-9)"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Harus ada karakter khusus (!@#$%...)"
    return True, "Password valid"

# Cek Email Terdaftar
def check_email_exists(supabase: Client, email: str) -> bool:
    """Cek apakah email sudah terdaftar"""
    try:
        response = supabase.table('users').select('email').eq('email', email).execute()
        return len(response.data) > 0
    except Exception:
        return False

# ⭐ PERBAIKAN: Handle Verification dari URL
def handle_verification():
    """Handle callback verifikasi dari email Supabase"""
    params = st.query_params

    if "access_token" not in params:
        return

    access_token = params.get("access_token", "")
    refresh_token = params.get("refresh_token", "")
    type_ = params.get("type", "")

    supabase = init_supabase()

    try:
        # kalau ada refresh_token → itu verify email signup
        if refresh_token:
            supabase.auth.set_session(access_token, refresh_token)

            user = supabase.auth.get_user()

            if user and user.user:
                supabase.table("users").update({"is_verified": True}).eq("id", user.user.id).execute()
                st.success("✅ Email berhasil diverifikasi!")

            supabase.auth.sign_out()
            st.query_params.clear()
            st.rerun()

        # kalau tidak ada refresh_token → ini reset password (recovery / magiclink)
        else:
            st.session_state.recovery_token = access_token
            st.session_state.page = "reset_password"
            st.query_params.clear()
            st.rerun()

    except Exception as e:
        st.error(f"❌ Verifikasi gagal: {e}")
        st.query_params.clear()


# Halaman Register
def register_page(supabase: Client, role: str):
    """Halaman registrasi dengan validasi lengkap"""
    st.header(f"📝 Registrasi - {role.capitalize()}")
    
    # Info password requirement
    with st.expander("ℹ️ Requirement Password"):
        st.markdown("""
        Password harus memenuhi:
        - ✓ Minimal 8 karakter
        - ✓ Mengandung huruf besar (A-Z)
        - ✓ Mengandung huruf kecil (a-z)
        - ✓ Mengandung angka (0-9)
        - ✓ Mengandung karakter khusus (!@#$%^&*...)
        """)
    
    with st.form("register_form"):
        email = st.text_input("📧 Email", placeholder="nama@example.com")
        password = st.text_input("🔒 Password", type="password")
        confirm_password = st.text_input("🔒 Konfirmasi Password", type="password")
        
        submitted = st.form_submit_button("✅ Daftar Sekarang", use_container_width=True, type="primary")
        
        if submitted:
            # Validasi input kosong
            if not email or not password or not confirm_password:
                st.error("❌ Semua field harus diisi!")
                return
            
            # Validasi format email
            if not validate_email(email):
                st.error("❌ Format email tidak valid!")
                return
            
            # Cek email sudah terdaftar
            if check_email_exists(supabase, email):
                st.error("❌ Email sudah terdaftar! Silakan login atau gunakan email lain.")
                return
            
            # Validasi password
            is_valid, message = validate_password(password)
            if not is_valid:
                st.error(f"❌ Password tidak valid: {message}")
                return
            
            # Cek password match
            if password != confirm_password:
                st.error("❌ Password tidak cocok!")
                return
            
            # Proses registrasi
            try:
                with st.spinner("Mendaftarkan akun..."):
                    app_url = get_app_url()
                    
                    # Sign up dengan Supabase Auth
                    response = supabase.auth.sign_up({
                        "email": email,
                        "password": password,
                        "options": {
                            "data": {"role": role},
                            "email_redirect_to": app_url
                        }
                    })
                    
                    time.sleep(1)
                    
                    # Simpan ke tabel users
                    if response.user:
                        supabase.table('users').insert({
                            "id": response.user.id,
                            "email": email,
                            "role": role,
                            "is_verified": False
                        }).execute()
                    
                    st.success("✅ Registrasi berhasil!")
                    st.info(f"📧 Email verifikasi telah dikirim ke **{email}**")
                    st.warning("⚠️ Silakan cek email Anda dan klik link verifikasi untuk mengaktifkan akun.")
                    
            except Exception as e:
                error_msg = str(e)
                if "already registered" in error_msg.lower():
                    st.error("❌ Email sudah terdaftar di sistem!")
                else:
                    st.error(f"❌ Registrasi gagal: {error_msg}")

# Halaman Login
def login_page(supabase: Client, role: str):
    """Halaman login dengan validasi role"""
    st.header(f"🔐 Login - {role.capitalize()}")
    
    with st.form("login_form"):
        email = st.text_input("📧 Email", placeholder="nama@example.com")
        password = st.text_input("🔒 Password", type="password")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            submitted = st.form_submit_button("🚀 Login", use_container_width=True, type="primary")
        with col2:
            forgot = st.form_submit_button("🔑 Lupa Password?", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("❌ Email dan password tidak boleh kosong!")
                return
            
            try:
                with st.spinner("Memproses login..."):
                    # Login dengan Supabase Auth
                    response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    # Ambil data user dari tabel
                    user_data = supabase.table('users').select('*').eq('id', response.user.id).single().execute()
                    
                    # Validasi role
                    if user_data.data['role'] != role:
                        st.error(f"❌ Login gagal! Anda terdaftar sebagai **{user_data.data['role']}**, bukan **{role}**")
                        supabase.auth.sign_out()
                        return
                    
                    # Cek verifikasi email
                    if not response.user.email_confirmed_at:
                        st.error("⚠️ Email Anda belum diverifikasi!")
                        st.warning("📧 Silakan cek email dan klik link verifikasi terlebih dahulu.")
                        st.info("💡 Tidak menerima email? Cek folder spam atau minta kirim ulang.")
                        supabase.auth.sign_out()
                        return
                    
                    # Login berhasil
                    st.success(f"✅ Login berhasil! Selamat datang, **{email}**")
                    st.session_state.user = response.user
                    st.session_state.user_data = user_data.data
                    st.session_state.role = role
                    st.session_state.logged_in = True
                    
                    time.sleep(1)
                    st.rerun()
                    
            except Exception as e:
                st.error("❌ Login gagal: Email atau password salah!")
                st.info("💡 Pastikan email sudah diverifikasi dan password benar.")
        
        if forgot:
            st.session_state.page = "forgot_password"
            st.rerun()

# Halaman Lupa Password
def forgot_password_page(supabase: Client):
    """Halaman request reset password"""
    st.header("🔑 Lupa Password")
    st.info("Masukkan email Anda untuk menerima link reset password.")

    with st.form("forgot_password_form"):
        email = st.text_input("📧 Email", placeholder="nama@example.com")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submitted = st.form_submit_button("📤 Kirim Email Reset", use_container_width=True, type="primary")
        with col2:
            back = st.form_submit_button("↩️ Kembali", use_container_width=True)
    
    if submitted:
        if not email:
            st.error("❌ Email tidak boleh kosong!")
        elif not validate_email(email):
            st.error("❌ Format email tidak valid!")
        else:
            try:
                with st.spinner("Mengirim email..."):
                    app_url = get_app_url()
                    
                    supabase.auth.reset_password_for_email(
                        email,
                        {"redirect_to": app_url}
                    )
                    
                    st.success(f"✅ Email reset password telah dikirim ke **{email}**")
                    st.info("📧 Silakan cek email dan klik link untuk mengubah password.")
                    st.warning("⚠️ Link hanya berlaku untuk beberapa waktu. Segera gunakan!")
                    
            except Exception as e:
                st.error(f"❌ Gagal mengirim email: {str(e)}")

    if back:
        st.session_state.page = "main"
        st.rerun()

# Halaman Reset Password
def reset_password_page(supabase: Client):
    """Halaman reset password dengan token dari email"""
    st.header("🔄 Reset Password")

    token = st.session_state.get("recovery_token")

    if not token:
        st.error("❌ Token reset password tidak ditemukan atau sudah expired!")
        st.info("💡 Silakan minta link reset password baru dari halaman login.")
        if st.button("↩️ Kembali ke Login"):
            st.session_state.page = "main"
            st.rerun()
        return

    # Info password requirement
    with st.expander("ℹ️ Requirement Password Baru"):
        st.markdown("""
        Password harus memenuhi:
        - ✓ Minimal 8 karakter
        - ✓ Mengandung huruf besar (A-Z)
        - ✓ Mengandung huruf kecil (a-z)
        - ✓ Mengandung angka (0-9)
        - ✓ Mengandung karakter khusus (!@#$%^&*...)
        """)

    with st.form("reset_password_form"):
        new_password = st.text_input("🔒 Password Baru", type="password")
        confirm_password = st.text_input("🔒 Konfirmasi Password Baru", type="password")
        submitted = st.form_submit_button("✅ Ubah Password", use_container_width=True, type="primary")

    if submitted:
        if not new_password or not confirm_password:
            st.error("❌ Semua field harus diisi!")
        else:
            is_valid, message = validate_password(new_password)
            if not is_valid:
                st.error(f"❌ Password tidak valid: {message}")
            elif new_password != confirm_password:
                st.error("❌ Password tidak cocok!")
            else:
                try:
                    with st.spinner("Mengubah password..."):
                        supabase.auth.set_session(st.session_state.recovery_token, "")
                        supabase.auth.update_user({"password": new_password})
                        
                        st.success("✅ Password berhasil diubah!")
                        st.info("🔐 Silakan login dengan password baru Anda.")
                        
                        # Clear token dan redirect
                        if 'recovery_token' in st.session_state:
                            del st.session_state.recovery_token
                        st.session_state.page = "main"
                        
                        time.sleep(2)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Gagal mengubah password: {str(e)}")
                    st.info("💡 Token mungkin sudah expired. Minta link reset password baru.")

# Halaman Dashboard
def dashboard_page(user, user_data):
    """Dashboard utama setelah login"""
    role = user_data['role']
    
    st.header(f"🎯 Dashboard - {role.capitalize()}")
    
    # Welcome message
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"👋 Selamat datang, **{user.email}**!")
    with col2:
        if st.button("🚪 Logout", type="primary", use_container_width=True):
            supabase = init_supabase()
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()
    
    st.divider()
    
    # Role-specific content
    if role == "akuntan":
        st.subheader("💼 Panel Akuntan")
        st.info("📊 Fitur: Laporan Keuangan, Jurnal, Buku Besar, dll.")
        
    elif role == "owner":
        st.subheader("👔 Panel Owner")
        st.info("📈 Fitur: Dashboard Analitik, Laporan Eksekutif, dll.")
        
    elif role == "karyawan":
        st.subheader("👷 Panel Karyawan")
        st.info("📝 Fitur: Input Kegiatan, Absensi, dll.")
        
    elif role == "kasir":
        st.subheader("💰 Panel Kasir")
        st.info("🧾 Fitur: Transaksi Penjualan, Kas Masuk/Keluar, dll.")
    
    st.warning("🚧 Sistem akuntansi sedang dalam pengembangan...")
    
    # Debug info
    with st.expander("🔧 Info Teknis (Debug)"):
        st.json({
            "user_id": user.id,
            "email": user.email,
            "role": role,
            "email_verified": user.email_confirmed_at is not None,
            "app_url": get_app_url()
        })

# Main Application
def main():
    """Aplikasi utama Tilapia Suite"""
    st.set_page_config(
        page_title="Tilapia Suite - Akuntansi Ikan Mujair",
        page_icon="🐟",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-title {
        text-align: center;
        color: #1E88E5;
        font-size: 3em;
        font-weight: bold;
        margin-bottom: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.2em;
        margin-top: 0;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<p class="main-title">🐟 Tilapia Suite</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Sistem Akuntansi Budidaya Ikan Mujair</p>', unsafe_allow_html=True)
    st.divider()
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Handle verification callback PERTAMA
    handle_verification()
    
    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state.page = 'main'
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # Routing berdasarkan state
    if st.session_state.logged_in and 'user' in st.session_state:
        dashboard_page(st.session_state.user, st.session_state.user_data)
        return
    
    if st.session_state.page == 'reset_password':
        reset_password_page(supabase)
        return
    
    if st.session_state.page == 'forgot_password':
        forgot_password_page(supabase)
        return
    
    # Role Selection
    if 'selected_role' not in st.session_state:
        st.subheader("👤 Pilih Role Anda")
        st.info("Silakan pilih role sesuai dengan posisi Anda di sistem.")
        
        roles = ["akuntan", "owner", "karyawan", "kasir"]
        role_icons = {"akuntan": "💼", "owner": "👔", "karyawan": "👷", "kasir": "💰"}
        role_desc = {
            "akuntan": "Mengelola laporan keuangan",
            "owner": "Melihat performa bisnis",
            "karyawan": "Input kegiatan harian",
            "kasir": "Transaksi penjualan"
        }
        
        cols = st.columns(4)
        for i, role in enumerate(roles):
            with cols[i]:
                if st.button(
                    f"{role_icons[role]}\n\n**{role.capitalize()}**\n\n{role_desc[role]}", 
                    key=f"role_{role}", 
                    use_container_width=True,
                    help=f"Login sebagai {role}"
                ):
                    st.session_state.selected_role = role
                    st.rerun()
    else:
        role = st.session_state.selected_role
        
        # Show selected role
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.success(f"✅ Role: **{role.capitalize()}**")
            if st.button("🔄 Ganti Role", use_container_width=True):
                del st.session_state.selected_role
                st.rerun()
        
        st.divider()
        
        # Login/Register tabs
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            login_page(supabase, role)
        
        with tab2:
            register_page(supabase, role)

if __name__ == "__main__":
    main()
