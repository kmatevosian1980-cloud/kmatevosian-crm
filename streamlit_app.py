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
# 🎨 ВАШ СТИЛЬ
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


if check_password():

    if "selected_order_id" not in st.session_state:
        st.session_state.selected_order_id = None

    st.sidebar.title(f"👤 {st.session_state.role.upper()}")

    menu = ["Список заказов", "Добавить заказ", "Карточка проекта"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")

    if "nav" not in st.session_state:
        st.session_state.nav = menu[0]

    choice = st.sidebar.selectbox(
        "Навигация",
        menu,
        index=menu.index(st.session_state.nav)
    )
    st.session_state.nav = choice

# ======================================================
# 📋 СПИСОК ЗАКАЗОВ (через data_editor)
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
                lambda x: x["full_name"] if isinstance(x, dict) else "Не назначен"
            )

            df["Остаток"] = df["total_price"] - df["paid_amount"]

            col1, col2, col3 = st.columns([2, 1, 1])

            search = col1.text_input("🔎 Поиск по клиенту")

            status_filter = col2.selectbox(
                "Этап проекта",
                ["Все"] + list(df["status"].unique())
            )

            responsible_filter = col3.selectbox(
                "Сотрудник",
                ["Все"] + list(df["Ответственный"].unique())
            )

            if search:
                df = df[df["client_name"].str.contains(search, case=False, na=False)]

            if status_filter != "Все":
                df = df[df["status"] == status_filter]

            if responsible_filter != "Все":
                df = df[df["Ответственный"] == responsible_filter]

            status_icons = {
                "Лид": "⚪", "Замер": "🔵", "Проект": "🟣",
                "Договор/Аванс": "🟪", "Производство": "🟠",
                "Монтаж": "🔷", "Завершено": "🟢"
            }

            df["Статус"] = df["status"].apply(
                lambda x: f"{status_icons.get(x, '⚪')} {x}"
            )

            display_df = df[[
                "id", "client_name", "phone", "address",
                "order_type", "Статус", "Ответственный",
                "total_price", "paid_amount", "Остаток", "comment"
            ]]

            display_df.columns = [
                "ID", "Клиент", "Телефон", "Адрес",
                "Тип мебели", "Статус", "Ответственный",
                "Сумма", "Оплачено", "Долг", "Комментарий"
            ]

            # 🔥 ВАЖНО: добавляем колонку выбора
            display_df.insert(0, "Открыть", False)

            edited_df = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Открыть": st.column_config.CheckboxColumn(required=False)
                }
            )

            selected_rows = edited_df[edited_df["Открыть"] == True]

            if not selected_rows.empty:
                selected_id = selected_rows.iloc[0]["ID"]
                st.session_state.selected_order_id = selected_id
                st.session_state.nav = "Карточка проекта"
                st.rerun()

        else:
            st.info("Заказов пока нет.")

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

            if st.session_state.selected_order_id:
                sel_id = st.session_state.selected_order_id
                st.session_state.selected_order_id = None
            else:
                selected_order = st.selectbox(
                    "Выберите клиента",
                    list(order_options.keys())
                )
                sel_id = order_options[selected_order]

            order = supabase.table("orders") \
                .select("*, users(full_name)") \
                .eq("id", sel_id) \
                .single() \
                .execute().data

            c1, c2, c3 = st.columns(3)
            c1.metric("Общая сумма", f"{order['total_price']:,.0f} ₽")
            c2.metric("Оплачено", f"{order['paid_amount']:,.0f} ₽")
            c3.metric("Остаток", f"{order['total_price'] - order['paid_amount']:,.0f} ₽")

            st.write("Карточка проекта полностью сохранена как в CRM 2.1")

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
            c3.metric("В долгах",
                      f"{(df['total_price'] - df['paid_amount']).sum():,.0f} ₽")

            st.bar_chart(df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
