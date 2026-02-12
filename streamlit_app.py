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
[data-testid="stForm"] {
    background-color: #ffffff;
    padding: 25px;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
}
[data-testid="stMetric"] {
    background-color: #ffffff;
    padding: 20px;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}
.stButton > button {
    border-radius: 10px;
    height: 45px;
    font-weight: 600;
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
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")

    choice = st.sidebar.selectbox("Навигация", menu)

    # ======================================================
    # 📋 СПИСОК ЗАКАЗОВ
    # ======================================================
    if choice == "Список заказов":

        st.title("📋 Все текущие проекты")

        orders_resp = supabase.table("orders") \
            .select("*, users(full_name)") \
            .order("id", desc=True) \
            .execute()

        if orders_resp.data:
            df = pd.DataFrame(orders_resp.data)

            # --- считаем оплаты через payments ---
            payments_resp = supabase.table("payments").select("*").execute()
            payments_df = pd.DataFrame(payments_resp.data) if payments_resp.data else pd.DataFrame()

            if not payments_df.empty:
                paid_sum = payments_df.groupby("order_id")["amount"].sum().reset_index()
                df = df.merge(paid_sum, how="left", left_on="id", right_on="order_id")
                df["amount"] = df["amount"].fillna(0)
            else:
                df["amount"] = 0

            df["Остаток"] = df["total_price"] - df["amount"]

            df["Ответственный"] = df["users"].apply(
                lambda x: x["full_name"] if isinstance(x, dict) else ""
            )

            # 🔎 Поиск и фильтр
            col1, col2 = st.columns([2, 1])
            search = col1.text_input("🔎 Поиск клиента")
            status_filter = col2.selectbox(
                "Фильтр по статусу",
                ["Все"] + list(df["status"].unique())
            )

            if search:
                df = df[df["client_name"].str.contains(search, case=False, na=False)]

            if status_filter != "Все":
                df = df[df["status"] == status_filter]

            status_icons = {
                "Лид": "⚪",
                "Замер": "🔵",
                "Проект": "🟣",
                "Производство": "🟠",
                "Монтаж": "🔷",
                "Завершено": "🟢"
            }

            df["Статус"] = df["status"].apply(
                lambda x: f"{status_icons.get(x, '⚪')} {x}"
            )

            display_df = df[[
                "id", "client_name", "Статус",
                "Ответственный", "total_price",
                "amount", "Остаток"
            ]]

            display_df.columns = [
                "ID", "Клиент", "Статус",
                "Ответственный", "Сумма",
                "Оплачено", "Остаток"
            ]

            st.dataframe(display_df, use_container_width=True)

        else:
            st.info("Заказов пока нет.")

    # ======================================================
    # 📝 КАРТОЧКА ПРОЕКТА
    # ======================================================
    elif choice == "Карточка проекта":

        st.title("🔎 Управление заказом")

        resp = supabase.table("orders").select("id, client_name").execute()

        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]

            order = supabase.table("orders") \
                .select("*, users(full_name)") \
                .eq("id", sel_id).single().execute().data

            # --- Получаем оплаты ---
            payments_resp = supabase.table("payments") \
                .select("*") \
                .eq("order_id", sel_id) \
                .order("payment_date", desc=True) \
                .execute()

            payments = payments_resp.data if payments_resp.data else []

            paid_total = sum(p["amount"] for p in payments)
            total = float(order["total_price"])
            debt = total - paid_total

            # KPI
            st.markdown(f"### {order['client_name']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Сумма договора", f"{total:,.0f} ₽")
            c2.metric("Оплачено", f"{paid_total:,.0f} ₽")
            c3.metric("Остаток", f"{debt:,.0f} ₽")

            st.divider()

            # ➕ Добавить оплату
            st.markdown("## ➕ Добавить оплату")

            with st.form("add_payment_form"):
                amount = st.number_input("Сумма", min_value=0.0, step=1000.0)
                payment_date = st.date_input("Дата оплаты", value=datetime.today())
                comment = st.text_input("Комментарий")

                submitted = st.form_submit_button("Сохранить оплату")

                if submitted and amount > 0:
                    supabase.table("payments").insert({
                        "order_id": sel_id,
                        "amount": amount,
                        "payment_date": payment_date.isoformat(),
                        "comment": comment
                    }).execute()

                    st.success("Оплата добавлена")
                    st.rerun()

            st.divider()

            # 📜 История оплат
            st.markdown("## 📜 История оплат")

            if payments:
                payments_df = pd.DataFrame(payments)
                payments_df["payment_date"] = pd.to_datetime(
                    payments_df["payment_date"]
                ).dt.strftime("%d.%m.%Y")

                display = payments_df[["payment_date","amount","comment"]]
                display.columns = ["Дата","Сумма","Комментарий"]

                st.dataframe(display, use_container_width=True)
            else:
                st.info("Оплат пока нет.")

    # ======================================================
    # 📊 АНАЛИТИКА
    # ======================================================
    elif choice == "Аналитика" and st.session_state.role == "admin":

        st.title("📊 Финансовый отчет")

        orders_resp = supabase.table("orders").select("*").execute()
        payments_resp = supabase.table("payments").select("*").execute()

        if orders_resp.data:
            orders_df = pd.DataFrame(orders_resp.data)
            payments_df = pd.DataFrame(payments_resp.data) if payments_resp.data else pd.DataFrame()

            total_revenue = orders_df["total_price"].sum()

            if not payments_df.empty:
                cash = payments_df["amount"].sum()
            else:
                cash = 0

            debt = total_revenue - cash

            c1, c2, c3 = st.columns(3)
            c1.metric("Оборот", f"{total_revenue:,.0f} ₽")
            c2.metric("Касса", f"{cash:,.0f} ₽")
            c3.metric("В долгах", f"{debt:,.0f} ₽")

            st.bar_chart(orders_df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
