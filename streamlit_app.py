import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# --- ПОДКЛЮЧЕНИЕ ---
# Убедитесь, что в Secrets Streamlit Cloud прописаны SUPABASE_URL и SUPABASE_KEY
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

    # --- 1. СПИСОК ЗАКАЗОВ (С ГИБКИМИ КОЛОНКАМИ) ---
    if choice == "Список заказов":
        st.subheader("📋 Все текущие проекты")
        resp = supabase.table("orders").select("*").order("id", desc=True).execute()
        
        if resp.data:
            df = pd.DataFrame(resp.data)
            df['Остаток'] = df['total_price'] - df['paid_amount']
            
            columns_map = {
                'id': 'ID', 'client_name': 'Клиент', 'phone': 'Телефон',
                'address': 'Адрес', 'order_type': 'Тип мебели', 'status': 'Статус',
                'total_price': 'Общая сумма', 'paid_amount': 'Оплачено',
                'Остаток': 'Остаток долга', 'created_at': 'Дата создания'
            }
            df_renamed = df.rename(columns=columns_map)
            
            with st.expander("⚙️ Настроить вид таблицы (выбрать колонки)"):
                default_cols = ['ID', 'Клиент', 'Статус', 'Общая сумма', 'Остаток долга']
                selected_cols = st.multiselect(
                    "Отображать колонки:",
                    options=list(columns_map.values()),
                    default=default_cols
                )
            
            if selected_cols:
                st.dataframe(df_renamed[selected_cols], use_container_width=True)
                if 'Общая сумма' in selected_cols:
                    st.caption(f"Всего заказов: {len(df_renamed)} | Сумма: {df_renamed['Общая сумма'].sum():,.0f} р.")
            else:
                st.warning("Выберите колонки.")
        else:
            st.info("Заказов пока нет.")

    # --- 2. ДОБАВЛЕНИЕ ЗАКАЗА ---
    elif choice == "Добавить заказ":
        st.subheader("🆕 Регистрация нового клиента")
        with st.form("new_order_form"):
            name = st.text_input("ФИО Клиента")
            phone = st.text_input("Телефон")
            address = st.text_area("Адрес доставки")
            o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф-купе", "Гардеробная", "Прихожая", "Другое"])
            price = st.number_input("Общая сумма (план)", min_value=0)
            
            if st.form_submit_button("Создать карточку"):
                new_data = {
                    "client_name": name, "phone": phone, "address": address,
                    "order_type": o_type, "total_price": price, "status": "Лид"
                }
                supabase.table("orders").insert(new_data).execute()
                st.success(f"Заказ для {name} создан!")
                st.rerun()

    # --- 3. КАРТОЧКА ПРОЕКТА (РЕДАКТОР И ФАЙЛЫ) ---
    elif choice == "Карточка проекта (Редактор)":
        st.subheader("🔍 Управление заказом")
        resp = supabase.table("orders").select("id, client_name").execute()
        
        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i['id'] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]
            
            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data
            
            tab1, tab2 = st.tabs(["📝 Информация", "📂 Файлы и Документы"])
            
            with tab1:
                with st.form("edit_pro_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        u_name = st.text_input("ФИО", value=order['client_name'])
                        u_phone = st.text_input("Телефон", value=order.get('phone', ''))
                        u_address = st.text_area("Адрес", value=order.get('address', ''))
