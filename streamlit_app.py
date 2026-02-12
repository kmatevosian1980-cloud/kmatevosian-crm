import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# ==============================
# 🔌 ПОДКЛЮЧЕНИЕ
# ==============================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

BUCKET_NAME = "furniture_files"

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# ==============================
# 🎨 СТИЛЬ
# ==============================
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }

.card {
    background: white;
    padding: 15px;
    border-radius: 14px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.06);
    margin-bottom: 12px;
}

.status-col {
    background: #f7f9fc;
    padding: 10px;
    border-radius: 16px;
    min-height: 500px;
}

.progress-bar {
    height: 8px;
    border-radius: 10px;
    background: #e5e7eb;
    overflow: hidden;
    margin-top: 6px;
}

.progress-fill {
    height: 8px;
    background: #4f46e5;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# 🔐 АВТОРИЗАЦИЯ
# ==============================
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False
        st.session_state.role = None

    if not st.session_state.auth:
        st.title("🔐 Вход в систему БиС Kitchen")
        user_type = st.selectbox("Выберите пользователя", ["Администратор", "Дизайнер/Замерщик"])
        pwd = st.text_input("Введите пароль", type="password")

        if st.button("Войти"):
            if user_type == "Администратор" and pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.role = "admin"
                st.rerun()
            elif user_type == "Дизайнер/Замерщик" and pwd == st.secrets.get("DESIGNER_PASSWORD", "12345"):
                st.session_state.auth = True
                st.session_state.role = "designer"
                st.rerun()
            else:
                st.error("Неверный пароль")
        return False
    return True

# ==============================
# 🚀 ОСНОВНОЙ ИНТЕРФЕЙС
# ==============================
if check_password():

    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Kanban-доска", "Список заказов", "Добавить заказ", "Карточка проекта"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")

    choice = st.sidebar.selectbox("Навигация", menu)

    statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]

    # ======================================================
    # 🧱 KANBAN
    # ======================================================
    if choice == "Kanban-доска":

        st.title("🧱 Kanban-доска заказов")

        resp = supabase.table("orders").select("*").execute()

        if resp.data:
            df = pd.DataFrame(resp.data)

            cols = st.columns(len(statuses))

            for i, status in enumerate(statuses):
                with cols[i]:
                    st.markdown(f"### {status}")
                    st.markdown('<div class="status-col">', unsafe_allow_html=True)

                    status_df = df[df["status"] == status]

                    for _, row in status_df.iterrows():
                        progress = 0
                        if row["total_price"] > 0:
                            progress = int((row["paid_amount"] / row["total_price"]) * 100)

                        st.markdown('<div class="card">', unsafe_allow_html=True)
                        st.markdown(f"**{row['client_name']}**")
                        st.write(f"💰 {row['total_price']:,.0f} ₽")
                        st.write(f"💳 {row['paid_amount']:,.0f} ₽")

                        st.markdown(f"""
                        <div class="progress-bar">
                            <div class="progress-fill" style="width:{progress}%"></div>
                        </div>
                        <small>{progress}% оплачено</small>
                        """, unsafe_allow_html=True)

                        if st.button("Открыть", key=f"open_{row['id']}"):
                            st.session_state.open_order = row["id"]
                            st.session_state.menu = "Карточка проекта"

                        st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)

    # ======================================================
    # 📋 СПИСОК
    # ======================================================
    elif choice == "Список заказов":
        st.title("📋 Все заказы")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            st.dataframe(pd.DataFrame(resp.data), use_container_width=True)

    # ======================================================
    # ➕ ДОБАВИТЬ
    # ======================================================
    elif choice == "Добавить заказ":
        st.title("➕ Новый заказ")

        with st.form("new_order"):
            name = st.text_input("Клиент")
            price = st.number_input("Сумма", min_value=0.0)
            if st.form_submit_button("Создать"):
                supabase.table("orders").insert({
                    "client_name": name,
                    "total_price": price,
                    "paid_amount": 0,
                    "status": "Лид"
                }).execute()
                st.success("Создано")
                st.rerun()

    # ======================================================
    # 📝 КАРТОЧКА
    # ======================================================
    elif choice == "Карточка проекта":
        st.title("📝 Карточка проекта")

        resp = supabase.table("orders").select("*").execute()

        if resp.data:
            options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            selected = st.selectbox("Выберите", list(options.keys()))
            sel_id = options[selected]

            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data

            total = float(order["total_price"])
            paid = float(order["paid_amount"])
            debt = total - paid

            c1, c2, c3 = st.columns(3)
            c1.metric("Общая сумма", f"{total:,.0f} ₽")
            c2.metric("Оплачено", f"{paid:,.0f} ₽")
            c3.metric("Остаток", f"{debt:,.0f} ₽")

            st.divider()

            tabs = st.tabs(["📝 Информация", "💰 История платежей", "📂 Файлы"])

            with tabs[1]:
                with st.form("add_pay"):
                    amount = st.number_input("Сумма", min_value=0.0)
                    comment = st.text_input("Комментарий")
                    if st.form_submit_button("Добавить"):
                        supabase.table("payments").insert({
                            "order_id": sel_id,
                            "amount": amount,
                            "comment": comment,
                            "payment_date": datetime.now().isoformat()
                        }).execute()

                        supabase.table("orders").update({
                            "paid_amount": paid + amount
                        }).eq("id", sel_id).execute()

                        st.rerun()

                pay_resp = supabase.table("payments").select("*").eq("order_id", sel_id).execute()
                if pay_resp.data:
                    st.dataframe(pd.DataFrame(pay_resp.data))

    # ======================================================
    # 📊 АНАЛИТИКА
    # ======================================================
    elif choice == "Аналитика":
        st.title("📊 Финансы")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.metric("Оборот", f"{df['total_price'].sum():,.0f} ₽")

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
