import streamlit as st
from supabase import create_client, Client
import pandas as pd

# ==============================
# 🔌 ПОДКЛЮЧЕНИЕ
# ==============================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

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

        resp = supabase.table("orders") \
            .select("*, users(full_name)") \
            .order("id", desc=True) \
            .execute()

        if resp.data:
            df = pd.DataFrame(resp.data)

            df["Ответственный"] = df["users"].apply(
                lambda x: x["full_name"] if isinstance(x, dict) else ""
            )

            df["Остаток"] = df["total_price"] - df["paid_amount"]

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
                "Договор/Аванс": "🟪",
                "Производство": "🟠",
                "Монтаж": "🔷",
                "Завершено": "🟢"
            }

            df["Статус"] = df["status"].apply(
                lambda x: f"{status_icons.get(x, '⚪')} {x}"
            )

            display_df = df[
                ["id", "client_name", "Статус",
                 "Ответственный", "total_price", "Остаток"]
            ]

            display_df.columns = [
                "ID", "Клиент", "Статус",
                "Ответственный", "Общая сумма", "Остаток"
            ]

            st.dataframe(display_df, use_container_width=True)

        else:
            st.info("Заказов пока нет.")

    # ======================================================
    # ➕ ДОБАВИТЬ ЗАКАЗ
    # ======================================================
    elif choice == "Добавить заказ":

        st.title("🆕 Новый заказ")

        users_resp = supabase.table("users").select("*").execute()
        users_list = users_resp.data if users_resp.data else []

        if not users_list:
            st.warning("⚠ Добавьте сотрудников в таблицу users.")
        else:
            user_dict = {u["full_name"]: u["id"] for u in users_list}

            with st.form("new_order_form"):

                name = st.text_input("ФИО Клиента")
                phone = st.text_input("Телефон")
                address = st.text_area("Адрес")
                o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф", "Гардеробная", "Другое"])
                price = st.number_input("Сумма", min_value=0)

                responsible_name = st.selectbox("Ответственный", list(user_dict.keys()))
                submit = st.form_submit_button("Создать заказ")

                if submit:
                    supabase.table("orders").insert({
                        "client_name": name,
                        "phone": phone,
                        "address": address,
                        "order_type": o_type,
                        "total_price": price,
                        "paid_amount": 0,
                        "status": "Лид",
                        "responsible_id": user_dict[responsible_name],
                        "comment": ""
                    }).execute()

                    st.success("Заказ создан!")
                    st.rerun()

    # ======================================================
    # 📝 КАРТОЧКА ПРОЕКТА
    # ======================================================
    elif choice == "Карточка проекта":

        st.title("🔎 Управление заказом")

        resp = supabase.table("orders").select("id, client_name").execute()

        if resp.data:
            order_options = {
                f"{i['client_name']} (ID:{i['id']})": i["id"]
                for i in resp.data
            }

            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]

            order = supabase.table("orders") \
                .select("*") \
                .eq("id", sel_id).single().execute().data

            total = float(order.get("total_price", 0))
            paid = float(order.get("paid_amount", 0))
            debt = total - paid

            st.markdown(f"### {order['client_name']}")
            st.divider()

            # KPI
            c1, c2, c3 = st.columns(3)
            c1.metric("Сумма договора", f"{total:,.0f} ₽")
            c2.metric("Оплачено", f"{paid:,.0f} ₽")
            c3.metric("Остаток", f"{debt:,.0f} ₽")

            st.divider()

            # ОДНА форма для финансов
            with st.form("finance_form"):

                col1, col2 = st.columns(2)

                with col1:
                    new_total = st.number_input(
                        "Сумма договора",
                        value=total,
                        min_value=0.0
                    )

                with col2:
                    payment_add = st.number_input(
                        "Добавить оплату",
                        min_value=0.0,
                        step=1000.0
                    )

                submit_finance = st.form_submit_button("Сохранить изменения")

                if submit_finance:

                    updated_paid = paid + payment_add

                    supabase.table("orders").update({
                        "total_price": new_total,
                        "paid_amount": updated_paid
                    }).eq("id", sel_id).execute()

                    st.success("Финансы обновлены")
                    st.rerun()

    # ======================================================
    # 📊 АНАЛИТИКА
    # ======================================================
    elif choice == "Аналитика" and st.session_state.role == "admin":

        st.title("📊 Финансовый отчет")

        resp = supabase.table("orders").select("*").execute()

        if resp.data:
            df = pd.DataFrame(resp.data)

            c1, c2, c3 = st.columns(3)
            c1.metric("Оборот", f"{df['total_price'].sum():,.0f} ₽")
            c2.metric("Касса", f"{df['paid_amount'].sum():,.0f} ₽")
            c3.metric(
                "В долгах",
                f"{(df['total_price'] - df['paid_amount']).sum():,.0f} ₽"
            )

            st.bar_chart(df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
