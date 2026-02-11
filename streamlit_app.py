import streamlit as st
from supabase import create_client, Client
import pandas as pd

# 1. Подключение к облачной базе через секреты
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# 2. Настройка страницы
st.set_page_config(page_title="BS Kitchen CRM", layout="wide")

# 3. Проверка пароля (берется из Secrets)
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.title("🔐 Вход в систему")
        pwd = st.text_input("Введите пароль", type="password")
        if st.button("Войти"):
            if pwd == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Неверный пароль")
        return False
    return True

if check_password():
    st.sidebar.title("Меню CRM")
    menu = ["Список заказов", "Добавить заказ", "Редактировать / Оплата", "Аналитика"]
    choice = st.sidebar.selectbox("Выберите действие", menu)

    # --- СПИСОК ЗАКАЗОВ ---
    if choice == "Список заказов":
        st.subheader("📋 Все текущие проекты")
        response = supabase.table("orders").select("*").order("id", desc=True).execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            df['Остаток'] = df['total_price'] - df['paid_amount']
            st.dataframe(df, use_container_width=True)
        else:
            st.info("В базе пока нет заказов.")

    # --- ДОБАВЛЕНИЕ НОВОГО ЗАКАЗА ---
    elif choice == "Добавить заказ":
        st.subheader("➕ Новый заказ на мебель")
        with st.form("new_order"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("ФИО Клиента")
                phone = st.text_input("Телефон")
                o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф", "Гардеробная", "Прихожая", "Другое"])
            with col2:
                price = st.number_input("Общая сумма заказа", min_value=0)
                paid = st.number_input("Внесенный аванс", min_value=0)
                status = st.selectbox("Статус", ["Лид", "Замер", "Проектирование", "Договор/Аванс", "Производство", "Монтаж", "Завершено"])
            
            if st.form_submit_button("Сохранить заказ"):
                data = {
                    "client_name": name, "phone": phone, "order_type": o_type,
                    "status": status, "total_price": price, "paid_amount": paid
                }
                supabase.table("orders").insert(data).execute()
                st.success("Данные успешно отправлены в облако!")

    # --- РЕДАКТИРОВАНИЕ ---
    elif choice == "Редактировать / Оплата":
        st.subheader("✏️ Обновление данных")
        resp = supabase.table("orders").select("id, client_name").execute()
        if resp.data:
            options = {f"{item['client_name']} (ID:{item['id']})": item['id'] for item in resp.data}
            selected = st.selectbox("Выберите проект", list(options.keys()))
            order_id = options[selected]
            
            curr = supabase.table("orders").select("*").eq("id", order_id).single().execute()
            d = curr.data
            
            with st.form("edit_form"):
                new_status = st.selectbox("Новый статус", ["Лид", "Замер", "Проектирование", "Договор/Аванс", "Производство", "Монтаж", "Завершено"], 
                                          index=["Лид", "Замер", "Проектирование", "Договор/Аванс", "Производство", "Монтаж", "Завершено"].index(d['status']))
                new_total = st.number_input("Общая сумма", value=float(d['total_price']))
                new_paid = st.number_input("Оплачено всего", value=float(d['paid_amount']))
                
                if st.form_submit_button("Обновить"):
                    supabase.table("orders").update({
                        "status": new_status, "total_price": new_total, "paid_amount": new_paid
                    }).eq("id", order_id).execute()
                    st.success("Данные обновлены!")
                    st.rerun()

    # --- АНАЛИТИКА ---
    elif choice == "Аналитика":
        st.subheader("📈 Финансовые показатели")
        response = supabase.table("orders").select("*").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            c1, c2, c3 = st.columns(3)
            c1.metric("Сумма всех заказов", f"{df['total_price'].sum():,.0f} р.")
            c2.metric("Получено денег", f"{df['paid_amount'].sum():,.0f} р.")
            debt = df['total_price'].sum() - df['paid_amount'].sum()
            c3.metric("Ожидаемые выплаты (долг)", f"{debt:,.0f} р.")
            st.bar_chart(df.groupby('status')['total_price'].sum())
