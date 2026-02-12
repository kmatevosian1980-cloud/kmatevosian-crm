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

BUCKET_NAME = "FURNITURE_FILES"

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# ==============================
# 🎨 СТИЛЬ
# ==============================
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
[data-testid="stForm"] { background-color: #ffffff; padding: 25px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }
[data-testid="stMetric"] { background-color: #ffffff; padding: 20px; border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
.stButton > button { border-radius: 10px; height: 45px; font-weight: 600; }
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
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")
    choice = st.sidebar.selectbox("Навигация", menu)

    # --- 📋 СПИСОК ЗАКАЗОВ ---
    if choice == "Список заказов":
        st.title("📋 Все текущие проекты")
        resp = supabase.table("orders").select("*, users(full_name)").order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            df["Ответственный"] = df["users"].apply(lambda x: x["full_name"] if isinstance(x, dict) else "")
            df["Остаток"] = df["total_price"] - df["paid_amount"]
            
            col1, col2 = st.columns([2, 1])
            search = col1.text_input("🔎 Поиск по имени клиента")
            status_filter = col2.selectbox("Фильтр по этапу", ["Все"] + list(df["status"].unique()))
            
            if search:
                df = df[df["client_name"].str.contains(search, case=False, na=False)]
            if status_filter != "Все":
                df = df[df["status"] == status_filter]
            
            st.dataframe(df[["id", "client_name", "status", "Ответственный", "total_price", "Остаток"]], use_container_width=True)
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
            price = st.number_input("Общая сумма договора", min_value=0.0)
            responsible_name = st.selectbox("Назначить ответственного", list(user_dict.keys()))
            
            if st.form_submit_button("🚀 Создать карточку заказа"):
                supabase.table("orders").insert({
                    "client_name": name, "phone": phone, "address": address,
                    "order_type": o_type, "total_price": price, "status": "Лид",
                    "responsible_id": user_dict[responsible_name], "paid_amount": 0
                }).execute()
                st.success(f"Заказ для {name} успешно создан!")
                st.rerun()

    # --- 📝 КАРТОЧКА ПРОЕКТА ---
    elif choice == "Карточка проекта":
        st.title("🔎 Управление заказом")
        resp = supabase.table("orders").select("id, client_name").execute()
        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]
            
            # Загрузка актуальных данных
            order = supabase.table("orders").select("*, users(full_name)").eq("id", sel_id).single().execute().data

            # Метрики сверху
            m1, m2, m3 = st.columns(3)
            m1.metric("Сумма договора", f"{order['total_price']:,.0f} ₽")
            m2.metric("Всего оплачено", f"{order['paid_amount']:,.0f} ₽")
            m3.metric("Остаток", f"{order['total_price'] - order['paid_amount']:,.0f} ₽")

            t_tab, s_tab, f_tab = st.tabs(["📝 Данные клиента", "💰 Финансы и История", "📂 Файлы"])

            with t_tab:
                users_resp = supabase.table("users").select("*").execute()
                u_dict = {u["full_name"]: u["id"] for u in users_resp.data}
                with st.form("edit_form"):
                    c1, c2 = st.columns(2)
                    u_phone = c1.text_input("Телефон", value=order.get("phone", ""))
                    u_address = c1.text_area("Адрес", value=order.get("address", ""))
                    statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]
                    u_status = c2.selectbox("Статус", statuses, index=statuses.index(order.get("status")))
                    u_resp = c2.selectbox("Ответственный", list(u_dict.keys()), 
                                          index=list(u_dict.values()).index(order.get("responsible_id")) if order.get("responsible_id") in u_dict.values() else 0)
                    u_comment = st.text_area("Комментарий к заказу", value=order.get("comment", ""))
                    if st.form_submit_button("💾 Сохранить изменения"):
                        supabase.table("orders").update({
                            "phone": u_phone, "address": u_address, "status": u_status, 
                            "responsible_id": u_dict[u_resp], "comment": u_comment
                        }).eq("id", sel_id).execute()
                        st.success("Данные обновлены!")
                        st.rerun()

            with s_tab:
                st.subheader("💰 Учет платежей")
                # Форма нового платежа
                with st.form("add_payment_form"):
                    p_col1, p_col2 = st.columns(2)
                    new_pay = p_col1.number_input("Сумма нового платежа (₽)", min_value=0.0)
                    new_comm = p_col2.text_input("Комментарий (н-р, 'Аванс наличными')")
                    if st.form_submit_button("✅ Добавить оплату"):
                        if new_pay > 0:
                            # 1. Запись в историю
                            supabase.table("payments").insert({"order_id": sel_id, "amount": new_pay, "comment": new_comm}).execute()
                            # 2. Обновление общего итога в orders
                            new_total_paid = float(order['paid_amount']) + new_pay
                            supabase.table("orders").update({"paid_amount": new_total_paid}).eq("id", sel_id).execute()
                            st.success("Платеж успешно добавлен!")
                            st.rerun()

                st.divider()
                st.write("### 📜 История всех оплат")
                pay_resp = supabase.table("payments").select("*").eq("order_id", sel_id).order("payment_date", desc=True).execute()
                if pay_resp.data:
                    pay_df = pd.DataFrame(pay_resp.data)
                    pay_df['Дата'] = pd.to_datetime(pay_df['payment_date']).dt.strftime('%d.%m.%Y %H:%M')
                    st.table(pay_df[['Дата', 'amount', 'comment']].rename(columns={'amount': 'Сумма (₽)', 'comment': 'Примечание'}))
                else:
                    st.info("Оплат по этому заказу еще не было.")

            with f_tab:
                st.subheader("📁 Чертежи и Фото")
                up_file = st.file_uploader("Прикрепить файл", type=['png', 'jpg', 'pdf'])
                if st.button("🚀 Загрузить в облако"):
                    if up_file:
                        path = f"{sel_id}/{up_file.name}"
                        supabase.storage.from_(BUCKET_NAME).upload(path, up_file.getvalue(), {"upsert": "true"})
                        st.success("Файл успешно прикреплен!")
                        st.rerun()
                
                # Список файлов
                try:
                    files = supabase.storage.from_(BUCKET_NAME).list(str(sel_id))
                    if files:
                        for f in files:
                            if f['name'] != '.emptyFolderPlaceholder':
                                url_f = supabase.storage.from_(BUCKET_NAME).get_public_url(f"{sel_id}/{f['name']}")
                                st.markdown(f"📄 [{f['name']}]({url_f})")
                except:
                    st.info("Файлы пока не загружены.")

    # --- 📊 АНАЛИТИКА ---
    elif choice == "Аналитика" and st.session_state.role == "admin":
        st.title("📊 Финансовый отчет")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            c1, c2, c3 = st.columns(3)
            c1.metric("Общий оборот", f"{df['total_price'].sum():,.0f} ₽")
            c2.metric("Касса (Всего)", f"{df['paid_amount'].sum():,.0f} ₽")
            c3.metric("Дебиторка (Долги)", f"{(df['total_price'] - df['paid_amount']).sum():,.0f} ₽")
            st.bar_chart(df["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
