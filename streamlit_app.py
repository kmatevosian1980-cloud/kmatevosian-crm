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

    if "selected_order_id" not in st.session_state:
        st.session_state.selected_order_id = None

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

        resp = supabase.table("orders").select("*, users(full_name)").order("id", desc=True).execute()

        if resp.data:
            df = pd.DataFrame(resp.data)

            df["Ответственный"] = df["users"].apply(
                lambda x: x["full_name"] if isinstance(x, dict) else "Не назначен"
            )

            df["Остаток"] = df["total_price"] - df["paid_amount"]

            display_df = df[[
                "id",
                "client_name",
                "status",
                "Ответственный",
                "total_price",
                "Остаток"
            ]]

            display_df.columns = [
                "ID",
                "Клиент",
                "Статус",
                "Ответственный",
                "Сумма",
                "Остаток"
            ]

            edited = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                disabled=True,
                key="orders_editor"
            )

            selected = st.session_state["orders_editor"]["selected_rows"]

            if selected:
                row_index = selected[0]
                selected_id = display_df.iloc[row_index]["ID"]
                st.session_state.selected_order_id = selected_id
                st.experimental_set_query_params(page="card")
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

            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}

            if st.session_state.selected_order_id:
                sel_id = st.session_state.selected_order_id
                st.session_state.selected_order_id = None
            else:
                selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
                sel_id = order_options[selected_order]

            order = supabase.table("orders").select("*, users(full_name)").eq("id", sel_id).single().execute().data

            # KPI
            c1, c2, c3 = st.columns(3)
            c1.metric("Общая сумма", f"{order['total_price']:,.0f} ₽")
            c2.metric("Оплачено", f"{order['paid_amount']:,.0f} ₽")
            c3.metric("Остаток", f"{order['total_price'] - order['paid_amount']:,.0f} ₽")

            tab_info, tab_pay, tab_files = st.tabs(["📝 Информация", "💰 История платежей", "📂 Файлы"])

            with tab_info:
                users_resp = supabase.table("users").select("*").execute()
                u_dict = {u["full_name"]: u["id"] for u in users_resp.data}

                with st.form("edit_form"):
                    col1, col2 = st.columns(2)

                    u_phone = col1.text_input("Телефон", value=order.get("phone", ""))
                    u_address = col1.text_area("Адрес", value=order.get("address", ""))

                    statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]
                    u_status = col2.selectbox("Статус", statuses, index=statuses.index(order.get("status")))

                    u_resp_name = col2.selectbox(
                        "Ответственный",
                        list(u_dict.keys()),
                        index=list(u_dict.values()).index(order.get("responsible_id"))
                        if order.get("responsible_id") in u_dict.values()
                        else 0
                    )

                    u_comment = st.text_area("Комментарий", value=order.get("comment", ""))

                    if st.form_submit_button("💾 Сохранить изменения"):
                        supabase.table("orders").update({
                            "phone": u_phone,
                            "address": u_address,
                            "status": u_status,
                            "responsible_id": u_dict[u_resp_name],
                            "comment": u_comment
                        }).eq("id", sel_id).execute()

                        st.success("Обновлено!")
                        st.rerun()
