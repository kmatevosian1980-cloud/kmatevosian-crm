import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# --- ПОДКЛЮЧЕНИЕ ---
# Данные берутся из настроек Secrets в Streamlit Cloud
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")

# --- СИСТЕМА ВХОДА (Учетные записи) ---
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False
        st.session_state.role = None

    if not st.session_state.auth:
        st.title("🔐 Вход в систему BS Kitchen")
        user_type = st.selectbox("Выберите пользователя", ["Администратор", "Дизайнер/Замерщик"])
        pwd = st.text_input("Введите пароль", type="password")
        
        if st.button("Войти"):
            # Проверка паролей из Secrets
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
    # Боковое меню навигации
    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта (Редактор)"]
    if st.session_state.role == "admin":
        menu.append("Аналитика")
    
    choice = st.sidebar.selectbox("Навигация", menu)

    # --- 1. СПИСОК ЗАКАЗОВ (С выбором колонок) ---
    if choice == "Список заказов":
        st.subheader("📋 Все текущие проекты")
        resp = supabase.table("orders").select("*").order("id", desc=True).execute()
        
        if resp.data:
            df = pd.DataFrame(resp.data)
            # Автоматический расчет долга
            df['Остаток'] = df['total_price'] - df['paid_amount']
            
            # Маппинг для красивых названий
            columns_map = {
                'id': 'ID',
                'client_name': 'Клиент',
                'phone': 'Телефон',
                'address': 'Адрес',
                'order_type': 'Тип мебели',
                'status': 'Статус',
                'total_price': 'Общая сумма',
                'paid_amount': 'Оплачено',
                'Остаток': 'Остаток долга',
                'created_at': 'Дата создания'
            }
            df_renamed = df.rename(columns=columns_map)
            
            # Настройка видимости колонок через разворачивающийся блок
            with st.expander("⚙️ Настроить вид таблицы (выбрать колонки)"):
                default_cols = ['ID', 'Клиент', 'Статус', 'Общая сумма', 'Остаток долга']
                selected_cols = st.multiselect(
                    "Отображать данные:",
                    options=list(columns_map.values()),
                    default=default_cols
                )
            
            if selected_cols:
                # Отображение таблицы со всеми заказами без фильтра по этапам
                st.dataframe(df_renamed[selected_cols], use_container_width=True)
                
                if 'Общая сумма' in selected_cols:
                    st.caption(f"Всего проектов: {len(df_renamed)} | Общая сумма: {df_renamed['Общая сумма'].sum():,.0f} р.")
            else:
                st.warning("Выберите хотя бы одну колонку для отображения.")
        else:
            st.info("Заказов пока нет.")

    # --- 2. ДОБАВЛЕНИЕ НОВОГО ЗАКАЗА ---
    elif choice == "Добавить заказ":
        st.subheader("🆕 Регистрация нового клиента")
        with st.form("new_order_form"):
            name = st.text_input("ФИО Клиента")
            phone = st.text_input("Телефон")
            address = st.text_area("Адрес доставки")
            o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф-купе", "Гардеробная", "Прихожая", "Другое"])
            price = st.number_input("Итоговая сумма (ориентир)", min_value=0)
            
            if st.form_submit_button("Создать карточку"):
                new_data = {
                    "client_name": name, "phone": phone, "address": address,
                    "order_type": o_type, "total_price": price, "status": "Лид"
                }
                supabase.table("orders").insert(new_data).execute()
                st.success(f"Проект для {name} успешно добавлен!")
                st.rerun()

    # --- 3. КАРТОЧКА ПРОЕКТА (Редактирование данных и файлов) ---
    elif choice == "Карточка проекта (Редактор)":
        st.subheader("🔍 Управление заказом")
        resp = supabase.table("orders").select("id, client_name").execute()
        
        if resp.data:
            order_options = {f"{i['client_name']} (ID:{i['id']})": i['id'] for i in resp.data}
            selected_order = st.selectbox("Выберите проект для редактирования", list(order_options.keys()))
            sel_id = order_options[selected_order]
            
            # Загрузка актуальных данных по выбранному ID
            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data
            
            tab1, tab2 = st.tabs(["📝 Изменить данные", "📂 Файлы и Чертежи"])
            
            with tab1:
                with st.form("edit_pro_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        u_name = st.text_input("ФИО клиента", value=order['client_name'])
                        u_phone = st.text_input("Телефон", value=order.get('phone', ''))
                        u_address = st.text_area("Адрес", value=order.get('address', ''))
                    with col2:
                        u_status = st.selectbox("Текущий этап", 
                            ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"],
                            index=["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"].index(order['status']))
                        u_price = st.number_input("Сумма договора", value=float(order['total_price']))
                        u_paid = st.number_input("Фактически оплачено", value=float(order['paid_amount']))
                        st.info(f"Остаток к получению: {u_price - u_paid} руб.")
                    
                    if st.form_submit_button("💾 Сохранить все изменения"):
                        supabase.table("orders").update({
                            "client_name": u_name, "phone": u_phone, "address": u_address,
                            "status": u_status, "total_price": u_price, "paid_amount": u_paid
                        }).eq("id", sel_id).execute()
                        st.success("Данные успешно обновлены!")
                        st.rerun()

            with tab2:
                st.write("### 📎 Хранилище документов")
                uploaded_file = st.file_uploader("Загрузить файл (Проект PDF, фото замера)", type=['png', 'jpg', 'pdf'])
                if st.button("🚀 Начать загрузку в облако"):
                    if uploaded_file:
                        file_path = f"{sel_id}/{uploaded_file.name}"
                        supabase.storage.from_("FURNITURE_FILES").upload(file_path, uploaded_file.getvalue(), {"upsert": "true"})
                        st.success("Файл успешно сохранен в карточке!")

    # --- 4. АНАЛИТИКА (Доступна только админу) ---
    elif choice == "Аналитика" and st.session_state.role == "admin":
        st.subheader("📊 Финансовые показатели")
        resp = supabase.table("orders").select("*").execute()
        if resp.data:
            df_an = pd.DataFrame(resp.data)
            c1, c2, c3 = st.columns(3)
            c1.metric("Общий оборот", f"{df_an['total_price'].sum():,.0f} р.")
            c2.metric("Собрано денег", f"{df_an['paid_amount'].sum():,.0f} р.")
            c3.metric("Долги клиентов", f"{(df_an['total_price'] - df_an['paid_amount']).sum():,.0f} р.")
            st.bar_chart(df_an['status'].value_counts())

    # Кнопка выхода в сайдбаре
    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.session_state.role = None
        st.rerun()
