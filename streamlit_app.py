import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- ПОДКЛЮЧЕНИЕ ---
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

BUCKET_NAME = "furniture_files"

st.set_page_config(page_title="BS Kitchen CRM Pro", layout="wide")


# =========================================================
# 🔐 АВТОРИЗАЦИЯ
# =========================================================
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


# =========================================================
# 🚀 ОСНОВНОЙ ИНТЕРФЕЙС
# =========================================================
if check_password():

    st.sidebar.title(f"👤 {st.session_state.role.upper()}")
    menu = ["Список заказов", "Добавить заказ", "Карточка проекта (Редактор)"]

    if st.session_state.role == "admin":
        menu.append("Аналитика")

    choice = st.sidebar.selectbox("Навигация", menu)

    # =========================================================
    # 📋 СПИСОК ЗАКАЗОВ
    # =========================================================
    if choice == "Список заказов":

        st.subheader("📋 Все текущие проекты")

        resp = supabase.table("orders") \
            .select("*, users(full_name)") \
            .order("id", desc=True) \
            .execute()

        if resp.data:
            df = pd.DataFrame(resp.data)

            df["Остаток"] = df["total_price"] - df["paid_amount"]

            # Получаем имя ответственного
            df["Ответственный"] = df["users"].apply(
                lambda x: x["full_name"] if isinstance(x, dict) else ""
            )

            columns_map = {
                "id": "ID",
                "client_name": "Клиент",
                "phone": "Телефон",
                "address": "Адрес",
                "order_type": "Тип мебели",
                "status": "Статус",
                "Ответственный": "Ответственный",
                "comment": "Комментарий",
                "total_price": "Общая сумма",
                "paid_amount": "Оплачено",
                "Остаток": "Остаток долга",
                "created_at": "Дата создания"
            }

            df_renamed = df.rename(columns=columns_map)

            with st.expander("⚙️ Настроить вид таблицы"):
                default_cols = ["ID", "Клиент", "Статус", "Ответственный", "Общая сумма", "Остаток долга"]
                selected_cols = st.multiselect(
                    "Отображать колонки:",
                    options=list(columns_map.values()),
                    default=default_cols
                )

            if selected_cols:
                st.dataframe(df_renamed[selected_cols], use_container_width=True)

                if "Общая сумма" in selected_cols:
                    st.caption(
                        f"Всего заказов: {len(df_renamed)} | "
                        f"Сумма: {df_renamed['Общая сумма'].sum():,.0f} р."
                    )

        else:
            st.info("Заказов пока нет.")

    # =========================================================
    # ➕ ДОБАВИТЬ ЗАКАЗ
    # =========================================================
    elif choice == "Добавить заказ":

        st.subheader("🆕 Регистрация нового клиента")

        users_resp = supabase.table("users").select("*").execute()
        users_list = users_resp.data if users_resp.data else []
        user_dict = {u["full_name"]: u["id"] for u in users_list}

        with st.form("new_order_form"):

            name = st.text_input("ФИО Клиента")
            phone = st.text_input("Телефон")
            address = st.text_area("Адрес доставки")
            o_type = st.selectbox("Тип мебели", ["Кухня", "Шкаф-купе", "Гардеробная", "Прихожая", "Другое"])
            price = st.number_input("Общая сумма (план)", min_value=0)

            responsible_name = st.selectbox("Ответственный", list(user_dict.keys()))
            responsible_id = user_dict[responsible_name]

            if st.form_submit_button("Создать карточку"):

                new_data = {
                    "client_name": name,
                    "phone": phone,
                    "address": address,
                    "order_type": o_type,
                    "total_price": price,
                    "paid_amount": 0,
                    "status": "Лид",
                    "responsible_id": responsible_id,
                    "comment": ""
                }

                supabase.table("orders").insert(new_data).execute()
                st.success("Заказ создан!")
                st.rerun()

    # =========================================================
    # 📝 КАРТОЧКА ПРОЕКТА
    # =========================================================
    elif choice == "Карточка проекта (Редактор)":

        st.subheader("🔍 Управление заказом")

        resp = supabase.table("orders").select("id, client_name").execute()

        if resp.data:

            order_options = {f"{i['client_name']} (ID:{i['id']})": i["id"] for i in resp.data}
            selected_order = st.selectbox("Выберите клиента", list(order_options.keys()))
            sel_id = order_options[selected_order]

            order = supabase.table("orders").select("*").eq("id", sel_id).single().execute().data

            tab1, tab2 = st.tabs(["📝 Информация", "📂 Файлы"])

            # -----------------------
            # Информация
            # -----------------------
            with tab1:

                users_resp = supabase.table("users").select("*").execute()
                users_list = users_resp.data if users_resp.data else []
                user_dict = {u["full_name"]: u["id"] for u in users_list}

                current_responsible_id = order.get("responsible_id")

                if current_responsible_id:
                    current_user_name = next(
                        (u["full_name"] for u in users_list if u["id"] == current_responsible_id),
                        None
                    )
                else:
                    current_user_name = list(user_dict.keys())[0]

                with st.form("edit_form"):

                    c1, c2 = st.columns(2)

                    with c1:
                        u_name = st.text_input("ФИО", value=order.get("client_name", ""))
                        u_phone = st.text_input("Телефон", value=order.get("phone", ""))
                        u_address = st.text_area("Адрес", value=order.get("address", ""))

                        u_responsible_name = st.selectbox(
                            "Ответственный",
                            options=list(user_dict.keys()),
                            index=list(user_dict.keys()).index(current_user_name)
                        )

                        u_responsible_id = user_dict[u_responsible_name]

                    with c2:
                        statuses = ["Лид", "Замер", "Проект", "Договор/Аванс", "Производство", "Монтаж", "Завершено"]
                        current_status = order.get("status", "Лид")
                        u_status = st.selectbox("Статус", statuses, index=statuses.index(current_status))

                        u_price = st.number_input("Сумма", value=float(order.get("total_price", 0)))
                        u_paid = st.number_input("Оплачено", value=float(order.get("paid_amount", 0)))

                        st.warning(f"Остаток: {u_price - u_paid} руб.")

                    u_comment = st.text_area("Комментарий", value=order.get("comment", ""))

                    if st.form_submit_button("💾 Сохранить"):

                        supabase.table("orders").update({
                            "client_name": u_name,
                            "phone": u_phone,
                            "address": u_address,
                            "responsible_id": u_responsible_id,
                            "status": u_status,
                            "total_price": u_price,
                            "paid_amount": u_paid,
                            "comment": u_comment
                        }).eq("id", sel_id).execute()

                        st.success("Обновлено!")
                        st.rerun()

            # -----------------------
            # Файлы
            # -----------------------
            with tab2:

                uploaded_file = st.file_uploader("Выберите файл", type=["png", "jpg", "pdf"])

                if st.button("🚀 Загрузить"):
                    if uploaded_file:
                        file_path = f"{sel_id}/{uploaded_file.name}"

                        supabase.storage.from_(BUCKET_NAME).upload(
                            file_path,
                            uploaded_file.getvalue(),
                            {"upsert": "true"}
                        )

                        st.success("Файл загружен!")
                        st.rerun()

                st.write("### 📂 Файлы:")

                try:
                    files_list = supabase.storage.from_(BUCKET_NAME).list(str(sel_id))

                    if files_list:
                        for f in files_list:
                            col1, col2 = st.columns([4, 1])
                            file_url = supabase.storage.from_(BUCKET_NAME).get_public_url(
                                f"{sel_id}/{f['name']}"
                            )
                            col1.write(f["name"])
                            col2.markdown(f"[Открыть]({file_url})")
                    else:
                        st.info("Файлов пока нет.")

                except Exception:
                    st.info("Папка ещё не создана.")

    # =========================================================
    # 📊 АНАЛИТИКА
    # =========================================================
    elif choice == "Аналитика" and st.session_state.role == "admin":

        st.subheader("📊 Финансовый отчет")

        resp = supabase.table("orders").select("*").execute()

        if resp.data:
            df_an = pd.DataFrame(resp.data)

            c1, c2, c3 = st.columns(3)

            c1.metric("Оборот", f"{df_an['total_price'].sum():,.0f} р.")
            c2.metric("Касса", f"{df_an['paid_amount'].sum():,.0f} р.")
            c3.metric("В долгах", f"{(df_an['total_price'] - df_an['paid_amount']).sum():,.0f} р.")

            st.bar_chart(df_an["status"].value_counts())

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
