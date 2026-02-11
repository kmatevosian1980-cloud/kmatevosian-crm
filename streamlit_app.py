import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# Подключение
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# --- УЧЕТНЫЕ ЗАПИСИ (СИСТЕМА ВХОДА) ---
# В Secrets добавьте: USER_ADMIN="пароль", USER_DESIGNER="пароль"
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False
        st.session_state.role = None

    if not st.session_state.auth:
        st.title("🔐 Вход в систему BS Kitchen")
        user = st.selectbox("Выберите пользователя", ["Администратор", "Дизайнер/Замерщик"])
        pwd = st.text_input("Введите пароль", type="password")
        
        if st.button("Войти"):
            # Проверка через Secrets
            if user == "Администратор" and pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.role = "admin"
                st.rerun()
            elif user == "Дизайнер/Замерщик" and pwd == st.secrets.get("DESIGNER_PASSWORD", "12345"):
                st.session_state.auth = True
                st.session_state.role = "designer"
                st.rerun()
            else:
                st.error("Неверный пароль")
        return False
    return True

if check_password():
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Поиск и Редактирование"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")
    
    choice = st.sidebar.selectbox("Меню", menu)

    # --- СПИСОК ЗАКАЗОВ ---
    if choice == "Список заказов":
        st.subheader("📋 Все проекты")
        resp = supabase.table("orders").select("*").order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df[['id', 'client_name', 'order_type', 'status', 'total_price', 'paid_amount']], use_container_width=True)

    # --- ДОБАВЛЕНИЕ ---
    elif choice == "Добавить заказ":
        with st.form("add_form"):
            st.subheader("🆕 Новый проект")
            name = st.text_input("Клиент")
            o_type = st.selectbox("Тип", ["Кухня", "Шкаф", "Корпусная мебель"])
            price = st.number_input("Сумма", min_value=0)
            if st.form_submit_button("Создать заказ"):
                supabase.table("orders").insert({"client_name": name, "order_type": o_type, "total_price": price, "status": "Лид"}).execute()
                st.success("Заказ создан!")

    # --- РЕДАКТИРОВАНИЕ И ФАЙЛЫ ---
    elif choice == "Поиск и Редактирование":
        st.subheader("🔍 Работа с карточкой заказа")
        resp = supabase.table("orders").select("id, client_name").execute()
        if resp.data:
            options = {f"{i['client_name']} (ID:{i['id']})": i['id'] for i in resp.data}
            sel_id = options[st.selectbox("Выберите заказ", list(options.keys()))]
            
            # Загружаем текущие данные
            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data
            
            tab1, tab2 = st.tabs(["📝 Данные карточки", "📂 Файлы и Проекты"])
            
            with tab1:
                with st.form("edit_form_pro"):
                    c1, c2 = st.columns(2)
                    new_name = c1.text_input("ФИО", value=order['client_name'])
                    new_phone = c1.text_input("Телефон", value=order.get('phone', ''))
                    new_status = c2.selectbox("Статус", ["Лид", "Замер", "Проект", "Производство", "Монтаж", "Завершено"], 
                                             index=["Лид", "Замер", "Проект", "Производство", "Монтаж", "Завершено"].index(order['status']))
                    new_price = c2.number_input("Общая сумма", value=float(order['total_price']))
                    new_paid = c2.number_input("Оплачено", value=float(order['paid_amount']))
                    
                    if st.form_submit_button("Сохранить все изменения"):
                        supabase.table("orders").update({
                            "client_name": new_name, "phone": new_phone, 
                            "status": new_status, "total_price": new_price, "paid_amount": new_paid
                        }).eq("id", sel_id).execute()
                        st.success("Данные обновлены!")

            with tab2:
                st.write("### Прикрепленные документы")
                uploaded_file = st.file_uploader("Загрузить фото замера или проект (PDF/JPG)", type=['png', 'jpg', 'pdf'])
                if st.button("Отправить файл"):
                    if uploaded_file:
                        file_path = f"{sel_id}/{uploaded_file.name}"
                        # Загрузка в Supabase Storage
                        supabase.storage.from_("furniture_files").upload(file_path, uploaded_file.getvalue())
                        st.success("Файл загружен!")
                
                # Список файлов (упрощенно)
                st.info("Файлы доступны в хранилище Supabase в папке по ID заказа.")

    st.sidebar.button("Выход", on_click=lambda: st.session_state.update({"auth": False}))
