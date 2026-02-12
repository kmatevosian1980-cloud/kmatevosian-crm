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
    # --- ЛОГИКА АВТО-ПЕРЕХОДА ---
    default_index = 0
    if "selected_order_id" in st.session_state and st.session_state.get("nav_trigger"):
        default_index = 2 # Индекс "Карточка проекта"
        st.session_state.nav_trigger = False

    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")

    choice = st.sidebar.selectbox("Навигация", menu, index=default_index)

    # --- 📋 СПИСОК ЗАКАЗОВ ---
    if choice == "Список заказов":
        st.title("📋 Все текущие проекты")
        resp = supabase.table("orders").select("*, users(full_name)").order("id", desc=True).execute()

        if resp.data:
            df = pd.DataFrame(resp.data)
            df["Ответственный"] = df["users"].apply(lambda x: x["full_name"] if isinstance(x, dict) else "Не назначен")
            df["Остаток"] = df["total_price"] - df["paid_amount"]

            c1, c2, c3 = st.columns([2, 1, 1])
            search = c1.text_input("🔎 Поиск клиента")
            status_f = c2.selectbox("Фильтр по статусу", ["Все"] + list(df["status"].unique()))
            resp_f = c3.selectbox("Сотрудник", ["Все"] + list(df["Ответственный"].unique()))

            if search:
                df = df[df["client_name"].str.contains(search, case=False, na=False)]
            if status_f != "Все":
                df = df[df["status"] == status_f]
            if resp_f != "Все":
                df = df[df["Ответственный"] == resp_f]

            status_icons = {"Лид": "⚪", "Замер": "🔵", "Проект": "🟣", "Договор/Аванс": "🟪", "Производство": "🟠", "Монтаж": "🔷", "Завершено": "🟢"}
            df["Статус_Отобр"] = df["status"].apply(lambda x: f"{status_icons.get(x, '⚪')} {x}")

            display_df = df[["id", "client_name", "phone", "address", "order_type", "Статус_Отобр", "Ответственный", "total_price", "paid_amount", "Остаток", "comment"]]
            display_df.columns = ["ID", "Клиент", "Телефон", "Адрес", "Тип мебели", "Статус", "Ответственный", "Сумма", "Оплачено", "Долг", "Комментарий"]

            st.info("💡 Кликните на строку в таблице, чтобы открыть карточку клиента")
            
            # ИНТЕРАКТИВНАЯ ТАБЛИЦА
            event = st.dataframe(
                display_df, 
                use_container_width=True, 
                hide_index=True,
                on_select="rerun",
                selection_mode="single_row"
            )

            if len(event.selection.rows) > 0:
                selected_row_idx = event.selection.rows[0]
                selected_id = df.iloc[selected_row_idx]['id']
                st.session_state.selected_order_id = selected_id
                st.session_state.nav_trigger = True
                st.rerun()

            st.caption(f"Отображено: {len(display_df)} | Сумма: {df['total_price'].sum():,.0f} ₽")
        else:
            st.info("Заказов пока нет.")

    # --- ➕ ДОБАВИТЬ ЗАКАЗ ---
    elif choice == "Добавить заказ":
        st.title("🆕 Новый заказ")
        users_resp = supabase.table("users").select("*").execute()
        user_dict = {u["full_name"]: u["id"] for u in users_resp.data} if users_resp.data else {}
        with st.form("new_order_form"):
            name = st.text_input("ФИО Клиента")
            phone = st.text_input("Телефон")
            address = st.text_area("Адрес")
            o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф", "Гардеробная", "Другое"])
            price = st.number_input("Сумма", min_value=0)
            resp_name = st.selectbox("Ответственный", list(user_dict.keys()))
            if st.form_submit_button("Создать заказ"):
                supabase.table("orders").insert({"client_name": name, "phone": phone, "address": address, "order_type": o_type, "total_price": price, "paid_amount": 0, "status": "Лид", "responsible_id": user_dict[resp_name]}).execute()
                st.success("Заказ создан!")
                st.rerun()

    # --- 📝 КАРТОЧКА ПРОЕКТА ---
    elif choice == "Карточка проекта":
        st.title("🔎 Управление заказом")
        resp = supabase.table("orders").select("id, client_name").execute()
        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            
            # Авто-подстановка ID при переходе из списка
            current_id = st.session_state.get("selected_order_id")
            default_sel = 0
            if current_id:
                for idx, (label, val) in enumerate(order_options.items()):
                    if val == current_id:
                        default_sel = idx
                        break

            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()), index=default_sel)
            sel_id = order_options[selected_order]
            order = supabase.table("orders").select("*, users(full_name)").eq("id", sel_id).single().execute().data

            c1, c2, c3 = st.columns(3)
            c1.metric("Общая сумма", f"{order['total_price']:,.0f} ₽")
            c2.metric("Оплачено", f"{order['paid_amount']:,.0f} ₽")
            c3.metric("Остаток", f"{order['total_price'] - order['paid_amount']:,.0f} ₽")

            tab_info, tab_pay, tab_files = st.tabs(["📝 Информация", "💰 История платежей", "📂 Файлы"])

            with tab_info:
                u_resp = supabase.table("users").select("*").execute()
                u_dict = {u["full_name"]: u["id"] for u in u_resp.data}
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    u_phone = col1.text_input("Телефон", value=order.get("phone", ""))
                    u_address = col1.text_area("Адрес", value=order.get("address", ""))
                    statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]
                    u_status = col2.selectbox("Статус", statuses, index=statuses.index(order.get("status")))
                    u_resp_name = col2.selectbox("Ответственный", list(u_dict.keys()), index=list(u_dict.values()).index(order.get("responsible_id")) if order.get("responsible_id") in u_dict.values() else 0)
                    u_comment = st.text_area("Комментарий", value=order.get("comment", ""))
                    if st.form_submit_button("💾 Сохранить изменения"):
                        supabase.table("orders").update({"phone": u_phone, "address": u_address, "status": u_status, "responsible_id": u_dict[u_resp_name], "comment": u_comment}).eq("id", sel_id).execute()
                        st.success("Обновлено!")
                        st.rerun()

            with tab_pay:
                with st.form("finance_form"):
                    p1, p2 = st.columns(2)
                    n_pay = p1.number_input("Сумма (₽)", min_value=0.0)
                    n_comm = p2.text_input("Комментарий (н-р, 'Аванс')")
                    if st.form_submit_button("✅ Зафиксировать платёж"):
                        if n_pay > 0:
                            supabase.table("payments").insert({"order_id": sel_id, "amount": n_pay, "comment": n_comm}).execute()
                            new_total = float(order['paid_amount']) + n_pay
                            supabase.table("orders").update({"paid_amount": new_total}).eq("id", sel_id).execute()
                            st.success("Платёж учтён!")
                            st.rerun()
                st.divider()
                pay_resp = supabase.table("payments").select("*").eq("order_id", sel_id).order("payment_date", desc=True).execute()
                if pay_resp.data:
                    p_df = pd.DataFrame(pay_resp.data)
                    p_df['Дата'] = pd.to_datetime(p_df['payment_date']).dt.strftime('%d.%m.%Y %H:%M')
                    st.table(p_df[['Дата', 'amount', 'comment']].rename(columns={'amount': 'Сумма', 'comment': 'Инфо'}))

            with tab_files:
                up_f = st.file_uploader("Загрузить файл", type=['png', 'jpg', 'pdf'])
                if st.button("🚀 Загрузить"):
                    if up_f:
                        path = f"{sel_id}/{up_f.name}"
                        supabase.storage.from_(BUCKET_NAME).upload(path, up_f.getvalue())
                        st.success("Загружено!")
                        st.rerun()
                files = supabase.storage.from_(BUCKET_NAME).list(str(sel_id))
                for f in files:
                    if f['name'] != '.emptyFolderPlaceholder':
                        url_f = supabase.storage.from_(BUCKET_NAME).get_public_url(f"{sel_id}/{f['name']}")
                        st.markdown(f"📄 [{f['name']}]({url_f})")

    # --- 📊 АНАЛИТИКА ---
    elif choice == "Аналитика" and st.session_state.role == "admin":
        st.title("📊 Финансовый отчет")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            c1, c2, c3 = st.columns(3)
            c1.metric("Оборот", f"{df['total_price'].sum():,.0f} ₽")
            c2.metric("Касса", f"{df['paid_amount'].sum():,.0f} ₽")
            c3.metric("Долги", f"{(df['total_price'] - df['paid_amount']).sum():,.0f} ₽")
            st.bar_chart(df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
