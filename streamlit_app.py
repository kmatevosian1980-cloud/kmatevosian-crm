import streamlit as st
from supabase import create_client, Client
import pandas as pd

# ==============================
# 🔌 ПОДКЛЮЧЕНИЕ
# ==============================
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

BUCKET_NAME = "furniture_files"

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# ==============================
# 🎨 ГЛОБАЛЬНЫЙ СТИЛЬ
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

h1, h2, h3 { font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ==============================
# 🟢 СТАТУС БЕЙДЖ
# ==============================
def status_badge(status):
    colors = {
        "Лид": "#9e9e9e",
        "Замер": "#2196f3",
        "Проект": "#9c27b0",
        "Договор/Аванс": "#673ab7",
        "Производство": "#ff9800",
        "Монтаж": "#03a9f4",
        "Завершено": "#4caf50"
    }
    color = colors.get(status, "#9e9e9e")

    return f"""
    <div style="
        display:inline-block;
        padding:6px 14px;
        border-radius:20px;
        background-color:{color};
        color:white;
        font-weight:600;
        font-size:14px;
    ">
        {status}
    </div>
    """

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

            # Ответственный
            df["Ответственный"] = df["users"].apply(
                lambda x: x["full_name"] if isinstance(x, dict) else ""
            )

            # Остаток
            df["Остаток долга"] = df["total_price"] - df["paid_amount"]

            # 🔎 Поиск + фильтр
            col1, col2 = st.columns([2,1])
            search = col1.text_input("🔎 Поиск клиента")
            status_filter = col2.selectbox(
                "Фильтр по статусу",
                ["Все"] + list(df["status"].unique())
            )

            if search:
                df = df[df["client_name"].str.contains(search, case=False, na=False)]

            if status_filter != "Все":
                df = df[df["status"] == status_filter]

            # Цветной статус
            df["Статус"] = df["status"].apply(lambda x: status_badge(x))

            display_df = df[[
                "id", "client_name", "Статус",
                "Ответственный", "total_price", "Остаток долга"
            ]]

            display_df.columns = [
                "ID", "Клиент", "Статус",
                "Ответственный", "Общая сумма", "Остаток"
            ]

            st.markdown(
                display_df.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

            st.caption(
                f"Всего заказов: {len(display_df)} | "
                f"Сумма: {df['total_price'].sum():,.0f} ₽"
            )

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
            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]

            order = supabase.table("orders") \
                .select("*, users(full_name)") \
                .eq("id", sel_id).single().execute().data

            # Заголовок
            colA, colB = st.columns([3,1])
            colA.markdown(f"### {order['client_name']}")
            colB.markdown(status_badge(order["status"]), unsafe_allow_html=True)

            st.divider()

            # 💰 KPI
            total = float(order.get("total_price", 0))
            paid = float(order.get("paid_amount", 0))
            debt = total - paid

            c1, c2, c3 = st.columns(3)
            c1.metric("Общая сумма", f"{total:,.0f} ₽")
            c2.metric("Оплачено", f"{paid:,.0f} ₽")
            c3.metric("Остаток", f"{debt:,.0f} ₽")

            st.divider()

            # Редактирование
            users_resp = supabase.table("users").select("*").execute()
            users_list = users_resp.data if users_resp.data else []
            user_dict = {u["full_name"]: u["id"] for u in users_list}

            with st.form("edit_form"):

                col1, col2 = st.columns(2)

                with col1:
                    u_phone = st.text_input("Телефон", value=order.get("phone", ""))
                    u_address = st.text_area("Адрес", value=order.get("address", ""))

                with col2:
                    statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]
                    u_status = st.selectbox("Статус", statuses,
                                            index=statuses.index(order.get("status")))

                    u_responsible_name = st.selectbox(
                        "Ответственный",
                        list(user_dict.keys())
                    )

                u_comment = st.text_area("Комментарий",
                                         value=order.get("comment", ""))

                submitted = st.form_submit_button("💾 Сохранить изменения")

                if submitted:
                    supabase.table("orders").update({
                        "phone": u_phone,
                        "address": u_address,
                        "status": u_status,
                        "responsible_id": user_dict[u_responsible_name],
                        "comment": u_comment
                    }).eq("id", sel_id).execute()

                    st.success("Обновлено!")
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
            c3.metric("В долгах",
                      f"{(df['total_price'] - df['paid_amount']).sum():,.0f} ₽")

            st.bar_chart(df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
