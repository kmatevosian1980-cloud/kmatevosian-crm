import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# --- ПОДКЛЮЧЕНИЕ ---
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# --- СИСТЕМА ВХОДА ---
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False
        st.session_state.role = None

    if not st.session_state.auth:
        st.title("🔐 Вход в систему BS Kitchen")
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
    # Боковое меню
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта (Редактор)"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")
    
    choice = st.sidebar.selectbox("Навигация", menu)

    # --- 1. СПИСОК ЗАКАЗОВ ---
    if choice == "Список заказов":
        st.subheader("📋 Все текущие проекты")
        resp = supabase.table("orders").select("*").order("id", desc=True).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            # Переименуем колонки для красоты
            df_view = df.rename(columns={
                'id': 'ID', 'client_name': 'Клиент', 'order_type': 'Тип', 
                'status': 'Статус', 'total_price': 'Сумма', 'paid_amount': 'Оплачено'
            })
            st.dataframe(df_view[['ID', 'Клиент', 'Тип', 'Статус', 'Сумма', 'Оплачено']], use_container_width=True)
        else:
            st.info("Заказов пока нет.")

    # --- 2. ДОБАВЛЕНИЕ ЗАКАЗА ---
    elif choice == "Добавить заказ":
        st.subheader("🆕 Регистрация нового клиента")
        with st.form("new_order_form"):
            name = st.text_input("ФИО Клиента")
            phone = st.text_input("Телефон")
            address = st.text_area("Адрес")
            o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф-купе", "Гардеробная", "Прихожая", "Офисная", "Другое"])
            price = st.number_input("Общая стоимость (план)", min_value=0)
            
            if st.form_submit_button("Создать карточку"):
                new_data = {
                    "client_name": name, "phone": phone, "address": address,
                    "order_type": o_type, "total_price": price, "status": "Лид"
                }
                supabase.table("orders").insert(new_data).execute()
                st.success(f"Заказ для {name} создан!")

    # --- 3. КАРТОЧКА ПРОЕКТА (РЕДАКТИРОВАНИЕ И ФАЙЛЫ) ---
    elif choice == "Карточка проекта (Редактор)":
        st.subheader("🔍 Управление заказом")
        resp = supabase.table("orders").select("id, client_name").execute()
        
        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i['id'] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента для работы", list(order_options.keys()))
            sel_id = order_options[selected_order]
            
            # Загружаем данные
            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data
            
            tab1, tab2 = st.tabs(["📝 Основная информация", "📂 Файлы и Чертежи"])
            
            with tab1:
                with st.form("edit_pro_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        u_name = st.text_input("ФИО", value=order['client_name'])
                        u_phone = st.text_input("Телефон", value=order.get('phone', ''))
                        u_address = st.text_area("Адрес доставки/замера", value=order.get('address', ''))
                    with col2:
                        u_status = st.selectbox("Статус проекта", 
                            ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"],
                            index=["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"].index(order['status']))
                        u_price = st.number_input("Итоговая сумма", value=float(order['total_price']))
                        u_paid = st.number_input("Внесено денег", value=float(order['paid_amount']))
                        st.warning(f"Остаток долга: {u_price - u_paid} руб.")
                    
                    if st.form_submit_button("💾 Сохранить изменения"):
                        supabase.table("orders").update({
                            "client_name": u_name, "phone": u_phone, "address": u_address,
                            "status": u_status, "total_price": u_price, "paid_amount": u_paid
                        }).eq("id", sel_id).execute()
                        st.success("Изменения сохранены в облаке!")
                        st.rerun()

            with tab2:
                st.write("### 📎 Документы по проекту")
                uploaded_file = st.file_uploader("Загрузить эскиз, договор или фото (PDF, JPG, PNG)", type=['png', 'jpg', 'jpeg', 'pdf'])
                
                if st.button("🚀 Начать загрузку"):
                    if uploaded_file:
                        # Путь: id_заказа/имя_файла
                        file_path = f"{sel_id}/{uploaded_file.name}"
                        file_data = uploaded_file.getvalue()
                        
                        try:
                            supabase.storage.from_("furniture_files").upload(file_path, file_data, {"upsert": "true"})
                            st.success(f"Файл {uploaded_file.name} успешно прикреплен!")
                        except Exception as e:
                            st.error(f"Ошибка загрузки: {e}")
                
                st.info("Просмотреть загруженные файлы можно в панели управления Supabase (раздел Storage -> furniture_files).")

    # --- 4. АНАЛИТИКА ---
    elif choice == "Аналитика" and st.session_state.role == "admin":
        st.subheader("📊 Финансовый отчет")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            c1, c2, c3 = st.columns(3)
            total = df['total_price'].sum()
            paid = df['paid_amount'].sum()
            c1.metric("Общий оборот", f"{total:,.0f} р.")
            c2.metric("Касса (получено)", f"{paid:,.0f} р.")
            c3.metric("В дебиторке (долги)", f"{total - paid:,.0f} р.")
            
            st.write("#### Распределение заказов по этапам")
            st.bar_chart(df['status'].value_counts())

    # Выход
    if st.sidebar.button("🚪 Выйти из системы"):
        st.session_state.auth = False
        st.session_state.role = None
        st.rerun()
