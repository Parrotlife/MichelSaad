import os
import sqlite3

import pandas as pd
import streamlit as st

DB_FILE = "votes_data.db"
EXCEL_FILE = "data/final--القاع-2025-filtered.xlsx"
TABLE_NAME = "voters"


def init_db():
    """Initializes the database. If the DB file exists, it does nothing.
    Otherwise, it loads data from the Excel file, adds an 'voter_id' column,
    adds a 'voted' column, and saves it to the SQLite DB."""
    if not os.path.exists(DB_FILE):
        try:
            df = pd.read_excel(EXCEL_FILE)
            # Define columns to drop
            columns_to_drop = ["البلدة أو الحي", "القضاء", "المحافظة", "الدائرة الانتخابية"]
            # Drop the specified columns, ignoring errors if a column doesn't exist
            df = df.drop(columns=columns_to_drop, errors="ignore")

            # Add a unique ID column at the beginning
            df.insert(0, "voter_id", range(len(df)))
            df["voted"] = False  # Add 'voted' column with default False
            conn = sqlite3.connect(DB_FILE)
            df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
            conn.close()
            st.success(f"Database initialized from {EXCEL_FILE}, 'voter_id' and 'voted' columns added.")
            st.session_state.db_just_initialized = True
        except Exception as e:
            st.error(f"Error initializing database: {e}")
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.stop()
    elif "db_just_initialized" not in st.session_state:
        st.session_state.db_just_initialized = False


def load_data_from_db():
    """Loads data from the SQLite database into a pandas DataFrame."""
    if not os.path.exists(DB_FILE):
        st.warning("ملف قاعدة البيانات غير موجود. يرجى التهيئة أو إعادة التعيين.")
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"خطأ في تحميل البيانات من قاعدة البيانات: {e}")
        return None


def update_voted_status(person_id, id_column_name, voted_status):  # id_column_name will be 'voter_id'
    """Updates the 'voted' status for a specific person in the database using voter_id."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # The id_column_name parameter is kept for consistency but should always be 'voter_id'
        query = f'UPDATE {TABLE_NAME} SET voted = ? WHERE "{id_column_name}" = ?'
        cursor.execute(query, (voted_status, person_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"خطأ في تحديث حالة التصويت للمعرف {person_id} ({id_column_name}): {e}")
        return False


def load_db_from_csv(uploaded_file):
    """Loads data from an uploaded CSV file and replaces the current database."""
    try:
        df_csv = pd.read_csv(uploaded_file)

        required_columns = ["voter_id", "voted"]
        missing_cols = [col for col in required_columns if col not in df_csv.columns]
        if missing_cols:
            st.error(f"ملف CSV المرفوع ينقصه الأعمدة المطلوبة: {', '.join(missing_cols)}")
            return False

        if "voter_id" in df_csv.columns:
            try:
                df_csv["voter_id"] = df_csv["voter_id"].astype(int)
            except ValueError:
                st.error("لا يمكن تحويل عمود 'voter_id' إلى أرقام صحيحة. يرجى التحقق من البيانات.")
                return False

        if "voted" in df_csv.columns:
            if df_csv["voted"].dtype != bool:
                try:
                    if df_csv["voted"].dtype == "object":
                        df_csv["voted"] = df_csv["voted"].replace(
                            {
                                "true": True,
                                "True": True,
                                "TRUE": True,
                                "false": False,
                                "False": False,
                                "FALSE": False,
                                "1": True,
                                1: True,
                                "0": False,
                                0: False,
                            }
                        )
                    df_csv["voted"] = df_csv["voted"].astype(bool)
                except Exception as e:
                    st.error(
                        f"لا يمكن تحويل عمود 'voted' ({df_csv['voted'].dtype}) إلى قيم منطقية: {e}. "
                        "يرجى التأكد أن القيم هي True/False."
                    )
                    return False

        conn = sqlite3.connect(DB_FILE)
        df_csv.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        conn.close()

        st.session_state.df_votes = None
        st.session_state.filtered_df_votes = None
        st.session_state.active_filters_votes = []
        st.session_state.db_just_initialized = True

        st.success("تم تحميل قاعدة البيانات بنجاح من ملف CSV.")
        return True

    except pd.errors.EmptyDataError:
        st.error("ملف CSV المرفوع فارغ.")
        return False
    except Exception as e:
        st.error(f"حدث خطأ أثناء تحميل قاعدة البيانات من CSV: {e}")
        return False


st.set_page_config(layout="wide")
st.title("تتبع الناخبين")

# --- Initialize DB on first run or if reset ---
init_db()

# --- Load data into session state ---
if "df_votes" not in st.session_state or st.session_state.get("db_just_initialized", False):
    st.session_state.df_votes = load_data_from_db()
    st.session_state.filtered_df_votes = st.session_state.df_votes
    st.session_state.active_filters_votes = []
    if "db_just_initialized" in st.session_state:  # Reset flag after loading
        st.session_state.db_just_initialized = False


# --- Main App Logic (only runs if data is successfully loaded) ---
if st.session_state.df_votes is not None and not st.session_state.df_votes.empty:
    df_original = st.session_state.df_votes
    columns_available = df_original.columns.tolist()

    # Set the ID column to our voter_id
    st.session_state.id_column_name = "voter_id"

    # Critical check: Ensure voter_id column exists in the loaded DataFrame
    if st.session_state.id_column_name not in df_original.columns:
        st.error(
            f"عمود المعرف الداخلي المطلوب ('{st.session_state.id_column_name}') مفقود. "
            "قد يكون هذا بسبب مخطط قاعدة بيانات قديم. "
            "يرجى إعادة تعيين قاعدة البيانات باستخدام زر 'إعادة تعيين قاعدة البيانات' في الشريط الجانبي."
        )
        # Clean up potentially problematic session state if we stop
        if os.path.exists(DB_FILE):  # If DB exists but is faulty
            st.warning("تم الكشف عن قاعدة بيانات معيبة.")
        # Allow app to render sidebar for reset
        # st.stop() # Consider if stopping here is best or allowing sidebar access.
        # Forcing a clear if essential ID is missing might be too much if user just wants to reset.
        # Let's ensure the app can at least show the sidebar for reset.
        # To prevent further errors, we can clear the dataframe from session state here.
        st.session_state.df_votes = None
        st.session_state.filtered_df_votes = None

    # Proceed only if df_votes is still valid (it might have been cleared above)
    if st.session_state.df_votes is not None and not st.session_state.df_votes.empty:
        st.sidebar.header("عوامل التصفية")

        # === START OF REPLACEMENT FOR SIDEBAR FILTERING UI ===
        st.sidebar.subheader("التصفية حسب حالة التصويت")  # Main subheader for filtering controls

        # --- START: New Radio Button Group for Vote Status Display ---
        if "permanent_vote_display_filter" not in st.session_state:
            st.session_state.permanent_vote_display_filter = "عرض الكل"

        vote_display_options = ["عرض الكل", "عرض من صوت فقط", "عرض من لم يصوت فقط"]
        st.session_state.permanent_vote_display_filter = st.sidebar.radio(
            "اختر حالة التصويت:",
            options=vote_display_options,
            index=vote_display_options.index(st.session_state.permanent_vote_display_filter),
            key="permanent_vote_display_filter_radio",
        )
        # --- END: New Radio Button Group ---

        # User's existing/desired structure for column-based filters follows
        st.sidebar.markdown("---")
        st.sidebar.subheader("عوامل تصفية أخرى")

        if st.sidebar.button("إضافة عامل تصفية", key="add_filter_btn_votes"):
            new_filter_id = pd.Timestamp.now().strftime("%Y%m%d%H%M%S%f")
            st.session_state.active_filters_votes.append({"id": new_filter_id, "column": "لا شيء", "values": []})
            st.rerun()

        filters_to_remove_votes = []
        for i, filt in enumerate(st.session_state.active_filters_votes):
            filter_id = filt["id"]
            st.sidebar.markdown("---")
            cols_with_none = ["لا شيء"] + [col for col in columns_available if col != "voted"]
            selected_column = st.sidebar.selectbox(
                "التصفية حسب العمود:",
                cols_with_none,
                index=cols_with_none.index(filt["column"]) if filt["column"] in cols_with_none else 0,
                key=f"filter_col_select_votes_{filter_id}",
            )
            if selected_column != filt["column"]:
                st.session_state.active_filters_votes[i]["column"] = selected_column
                st.session_state.active_filters_votes[i]["values"] = []
                st.rerun()
            if selected_column != "لا شيء":
                if selected_column in df_original.columns:
                    # Calculate value counts and sort unique values by frequency
                    value_counts = df_original[selected_column].value_counts()
                    options_sorted_by_count = value_counts.index.tolist()

                    display_options = []
                    if options_sorted_by_count:
                        try:
                            display_options = [str(v) for v in options_sorted_by_count]
                        except Exception as e_conv:
                            st.warning(f"خطأ في تحويل خيار التصفية لـ '{selected_column}': {e_conv}. تأثرت الخيارات.")
                            # Fallback to unique values if string conversion of value_counts index fails for some reason
                            try:
                                unique_values_fallback = df_original[selected_column].dropna().unique().tolist()
                                display_options = [str(v) for v in unique_values_fallback if pd.notna(v)]
                            except Exception as e_fallback_conv:
                                st.error(f"خطأ حرج في تحويل خيار التصفية لـ '{selected_column}': {e_fallback_conv}")

                    multiselect_label = f"قيم لـ '{selected_column}' (حسب العدد):"

                    selected_values = st.sidebar.multiselect(
                        multiselect_label,
                        options=display_options,
                        default=filt[
                            "values"
                        ],  # Assumes filt["values"] are strings, which they should be from previous selections
                        key=f"filter_val_multiselect_votes_{filter_id}",
                    )
                    if selected_values != filt["values"]:
                        st.session_state.active_filters_votes[i]["values"] = selected_values
                else:
                    st.sidebar.warning(
                        f"لم يتم العثور على العمود '{selected_column}' للتصفية. ربما تمت إزالته أو تغييره."
                    )

            if st.sidebar.button(f"إزالة عامل التصفية {i+1}", key=f"remove_filter_votes_{filter_id}"):
                filters_to_remove_votes.append(i)

        if filters_to_remove_votes:
            for index in sorted(filters_to_remove_votes, reverse=True):
                del st.session_state.active_filters_votes[index]
            st.rerun()

        st.sidebar.markdown("---")
        col1_sidebar, col2_sidebar = st.sidebar.columns(2)
        apply_filters_button_votes = col1_sidebar.button("تطبيق عوامل التصفية", key="apply_filters_btn_votes")
        reset_filters_button_votes = col2_sidebar.button("إعادة تعيين عوامل التصفية", key="reset_filters_btn_votes")

        if apply_filters_button_votes:
            temp_df = df_original.copy()
            filters_applied_count = 0
            try:
                for filt in st.session_state.active_filters_votes:
                    col = filt["column"]
                    vals = filt["values"]
                    if col != "لا شيء" and vals and col in temp_df.columns:  # Added check col in temp_df.columns
                        col_type = df_original[col].dtype
                        try:
                            if pd.api.types.is_numeric_dtype(col_type):
                                converted_vals = []
                                for v in vals:
                                    try:
                                        converted_vals.append(pd.to_numeric(v))
                                    except ValueError:
                                        st.warning(f"تعذر تحويل '{v}' إلى رقم لـ '{col}'.")
                                if not converted_vals:
                                    continue
                                temp_df = temp_df[temp_df[col].isin(converted_vals)]
                            elif pd.api.types.is_datetime64_any_dtype(col_type):
                                converted_vals = [pd.to_datetime(v, errors="coerce") for v in vals]
                                converted_vals = [v for v in converted_vals if pd.notnull(v)]
                                if not converted_vals:
                                    continue
                                temp_df = temp_df[temp_df[col].isin(converted_vals)]
                            else:
                                temp_df = temp_df[temp_df[col].astype(str).isin(map(str, vals))]
                        except Exception as e_filter_type:
                            st.warning(
                                f"خطأ في التصفية على '{col}' بـ '{vals}': {e_filter_type}. باستخدام مطابقة السلسلة."
                            )
                            temp_df = temp_df[temp_df[col].astype(str).isin(map(str, vals))]
                        filters_applied_count += 1
                    elif col not in temp_df.columns and col != "لا شيء":
                        st.warning(f"عمود التصفية '{col}' غير موجود. يتم تخطي عامل التصفية هذا.")

                st.session_state.filtered_df_votes = temp_df
                if filters_applied_count > 0:
                    st.sidebar.success(f"تم تطبيق {filters_applied_count} عامل (عوامل) تصفية.")
                else:
                    st.sidebar.info("لا توجد عوامل تصفية نشطة. يتم عرض جميع البيانات.")
                if filters_applied_count == 0:
                    st.session_state.filtered_df_votes = df_original  # Ensure reset if no filters actually applied
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"خطأ في تطبيق عوامل التصفية: {e}")

        if reset_filters_button_votes:
            perform_reset = bool(st.session_state.active_filters_votes)
            if not perform_reset:
                if st.session_state.filtered_df_votes is None or (
                    df_original is not None and not st.session_state.filtered_df_votes.equals(df_original)
                ):
                    perform_reset = True
                elif df_original is None and st.session_state.filtered_df_votes is not None:
                    perform_reset = True
            if perform_reset:
                st.session_state.active_filters_votes = []
                st.session_state.filtered_df_votes = df_original
                st.sidebar.info("تمت إعادة تعيين جميع عوامل التصفية. يتم عرض جميع البيانات.")
                st.rerun()
            else:
                st.sidebar.info("لا توجد عوامل تصفية لإعادة تعيينها.")

        # --- Load Database from CSV ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("تحميل قاعدة البيانات من ملف CSV")
        uploaded_csv_file = st.sidebar.file_uploader("اختر ملف CSV لتحميله:", type=["csv"], key="csv_uploader")

        if uploaded_csv_file is not None:
            if st.sidebar.button("تحميل من CSV واستبدال", key="load_csv_btn"):
                if load_db_from_csv(uploaded_csv_file):
                    st.rerun()

        # --- Reset Database ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("إعادة تعيين قاعدة البيانات")
        st.sidebar.warning("سيؤدي هذا إلى حذف قاعدة البيانات الحالية والبدء من جديد. يرجى التأكد قبل المتابعة.")

        if st.sidebar.button("إعادة تعيين قاعدة البيانات", key="reset_db_btn"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.session_state.clear()
            st.success("تمت إعادة تعيين قاعدة البيانات. سيتم إعادة تحميل البيانات. يرجى إعادة التشغيل إذا لزم الأمر.")
            st.rerun()

        st.header("قائمة الناخبين")
        if st.session_state.filtered_df_votes is not None:
            # --- Calculate and Display Vote Counts (based on st.session_state.filtered_df_votes) ---
            if not st.session_state.filtered_df_votes.empty:
                total_in_filtered = len(st.session_state.filtered_df_votes)
                if "voted" in st.session_state.filtered_df_votes.columns:
                    voted_in_filtered = st.session_state.filtered_df_votes["voted"].astype(bool).sum()
                    col1_count, col2_count = st.columns(2)
                    with col1_count:
                        st.metric(label="صوّت (حسب عوامل تصفية المستخدم)", value=voted_in_filtered)
                    with col2_count:
                        st.metric(label="المجموع (حسب عوامل تصفية المستخدم)", value=total_in_filtered)
                    st.markdown("---")
                else:
                    st.warning("عمود 'voted' مفقود، لا يمكن عرض عدد الأصوات.")
            else:
                st.info("لا يوجد ناخبون في العرض الحالي المصفى من قبل المستخدم لعدهم.")  # Clarified message

            # --- Prepare DataFrame for st.data_editor (df_for_editor) ---
            # Start with a copy of the dynamically filtered data
            df_for_editor = st.session_state.filtered_df_votes.copy()

            # Apply the permanent vote display filter based on radio button selection
            if st.session_state.permanent_vote_display_filter == "عرض من صوت فقط":
                if "voted" in df_for_editor.columns:
                    df_for_editor = df_for_editor[df_for_editor["voted"].astype(bool)].copy()
            elif st.session_state.permanent_vote_display_filter == "عرض من لم يصوت فقط":
                if "voted" in df_for_editor.columns:
                    df_for_editor = df_for_editor[~df_for_editor["voted"].astype(bool)].copy()
            # If "Show All", no further filtering is done on df_for_editor here.

            df_display = df_for_editor

            if "voted" in df_display.columns:
                df_display["voted"] = df_display["voted"].astype(bool)
            else:
                st.error("حرج: عمود 'voted' مفقود من بيانات العرض. لا يمكن المتابعة في التعديل.")
                st.stop()

            edited_df = st.data_editor(
                df_display,
                column_config={
                    "voted": st.column_config.CheckboxColumn(
                        "تم التصويت؟",  # User's preferred label
                        default=False,
                    )
                },
                # Make all columns non-editable except 'voted'
                disabled=[col for col in df_display.columns if col != "voted"],
                key="data_editor_votes",
                num_rows="dynamic",
            )

            # --- Detect changes and update DB ---
            # Compare edited_df with df_display (what was actually sent to the editor)
            if not edited_df.equals(df_display):
                # Merge edited_df (potentially a subset if "show_not_voted_filter" was on)
                # with st.session_state.filtered_df_votes (the broader context from dynamic filters)
                # to correctly identify original 'voted' status for comparison.
                comparison_df = st.session_state.filtered_df_votes.merge(
                    edited_df,  # Contains voter_id and new 'voted_edited' status from the editor
                    on=st.session_state.id_column_name,
                    suffixes=("_orig", "_edited"),
                    how="inner",  # Ensures we only process rows that were actually in edited_df (i.e., displayed)
                )
                changed_rows = comparison_df[comparison_df["voted_orig"] != comparison_df["voted_edited"]]
                if not changed_rows.empty:
                    updated_ids_count = 0
                    for _, row in changed_rows.iterrows():
                        person_app_id = row[st.session_state.id_column_name]
                        new_voted_status = row["voted_edited"]
                        if update_voted_status(person_app_id, st.session_state.id_column_name, new_voted_status):
                            updated_ids_count += 1
                        else:
                            st.warning(f"فشل تحديث حالة التصويت لمعرف التطبيق {person_app_id} في قاعدة البيانات.")
                    if updated_ids_count > 0:
                        st.success(f"تم تحديث حالة التصويت لـ {updated_ids_count} ناخب (ناخبين) في قاعدة البيانات.")
                        st.session_state.df_votes = load_data_from_db()
                        if st.session_state.df_votes is None:
                            st.error("فشل إعادة تحميل البيانات من قاعدة البيانات بعد التحديث. خطأ حرج.")
                            st.session_state.filtered_df_votes = pd.DataFrame()
                            st.session_state.active_filters_votes = []
                            st.rerun()  # Try to reset to a somewhat stable state
                        else:
                            # Re-apply filters
                            temp_df_after_update = st.session_state.df_votes.copy()
                            current_filters = st.session_state.active_filters_votes
                            if current_filters:
                                for filt_reapply in current_filters:
                                    col_reapply = filt_reapply["column"]
                                    vals_reapply = filt_reapply["values"]
                                    if (
                                        col_reapply != "لا شيء"
                                        and vals_reapply
                                        and col_reapply in temp_df_after_update.columns
                                    ):
                                        # Simplified re-application; assumes types are fine from previous application
                                        try:
                                            col_type_reapply = temp_df_after_update[col_reapply].dtype
                                            if pd.api.types.is_numeric_dtype(col_type_reapply):
                                                converted_vals_reapply = [pd.to_numeric(v) for v in vals_reapply]
                                                temp_df_after_update = temp_df_after_update[
                                                    temp_df_after_update[col_reapply].isin(converted_vals_reapply)
                                                ]
                                            else:
                                                temp_df_after_update = temp_df_after_update[
                                                    temp_df_after_update[col_reapply]
                                                    .astype(str)
                                                    .isin(map(str, vals_reapply))
                                                ]
                                        except Exception as e_reapply:
                                            st.error(
                                                f"خطأ في إعادة تطبيق عامل التصفية على '{col_reapply}': {e_reapply}"
                                            )
                            st.session_state.filtered_df_votes = temp_df_after_update
                            st.rerun()
            st.write(f"عرض {len(edited_df)} ناخب (ناخبين).")
        else:
            st.info("لا توجد بيانات لعرضها. قد تحتاج إلى إعادة تعيين قاعدة البيانات أو التحقق من ملف Excel.")
    # This else corresponds to if df_votes became None due to missing voter_id
    else:  # This handles the case where df_votes is None from the start or after a critical error
        st.error(
            "لا يمكن تحميل بيانات الناخبين. يرجى التحقق من وجود ملف قاعدة البيانات "
            "أو إعادة تعيين قاعدة البيانات إذا استمرت المشكلة."
        )
        # Optionally, provide a button to attempt re-initialization or guide the user.
        if st.button("محاولة إعادة تهيئة قاعدة البيانات"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.session_state.clear()
            st.rerun()

# Placeholder for any additional UI elements or logic outside the main data-dependent block.
# For example, a global footer or help section could go here.
else:  # This handles the case where df_votes is None from the start
    st.error("فشل تحميل بيانات الناخبين عند بدء التشغيل. حاول إعادة تعيين قاعدة البيانات.")
    if st.sidebar.button("إعادة تعيين قاعدة البيانات الآن"):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        st.session_state.clear()  # Clear session state to trigger re-initialization
        st.rerun()
