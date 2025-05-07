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
        st.warning("Database file not found. Please initialize or reset.")
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error loading data from database: {e}")
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
        st.error(f"Error updating voted status for ID {person_id} ({id_column_name}): {e}")
        return False


st.set_page_config(layout="wide")
st.title("Voter Tracking")

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
            f"The required internal ID column ('{st.session_state.id_column_name}') is missing. "
            "This might be due to an outdated database schema. "
            "Please reset the database using the 'Reset Database' button in the sidebar."
        )
        # Clean up potentially problematic session state if we stop
        if os.path.exists(DB_FILE):  # If DB exists but is faulty
            st.warning("Faulty database detected.")
        # Allow app to render sidebar for reset
        # st.stop() # Consider if stopping here is best or allowing sidebar access.
        # Forcing a clear if essential ID is missing might be too much if user just wants to reset.
        # Let's ensure the app can at least show the sidebar for reset.
        # To prevent further errors, we can clear the dataframe from session state here.
        st.session_state.df_votes = None
        st.session_state.filtered_df_votes = None

    # Proceed only if df_votes is still valid (it might have been cleared above)
    if st.session_state.df_votes is not None and not st.session_state.df_votes.empty:
        st.sidebar.header("Options")

        st.sidebar.subheader("Filter Data")
        if st.sidebar.button("Add Filter", key="add_filter_btn_votes"):
            new_filter_id = pd.Timestamp.now().strftime("%Y%m%d%H%M%S%f")
            st.session_state.active_filters_votes.append({"id": new_filter_id, "column": "None", "values": []})
            st.rerun()

        filters_to_remove_votes = []
        for i, filt in enumerate(st.session_state.active_filters_votes):
            filter_id = filt["id"]
            st.sidebar.markdown("---")
            cols_with_none = ["None"] + [col for col in columns_available if col != "voted"]
            selected_column = st.sidebar.selectbox(
                "Filter by column:",
                cols_with_none,
                index=cols_with_none.index(filt["column"]) if filt["column"] in cols_with_none else 0,
                key=f"filter_col_select_votes_{filter_id}",
            )
            if selected_column != filt["column"]:
                st.session_state.active_filters_votes[i]["column"] = selected_column
                st.session_state.active_filters_votes[i]["values"] = []
                st.rerun()
            if selected_column != "None":
                if selected_column in df_original.columns:
                    # Calculate value counts and sort unique values by frequency
                    value_counts = df_original[selected_column].value_counts()
                    options_sorted_by_count = value_counts.index.tolist()

                    display_options = []
                    if options_sorted_by_count:
                        try:
                            display_options = [str(v) for v in options_sorted_by_count]
                        except Exception as e_conv:
                            st.warning(
                                f"Filter opt conversion err for '{selected_column}': {e_conv}. Options affected."
                            )
                            # Fallback to unique values if string conversion of value_counts index fails for some reason
                            try:
                                unique_values_fallback = df_original[selected_column].dropna().unique().tolist()
                                display_options = [str(v) for v in unique_values_fallback if pd.notna(v)]
                            except Exception as e_fallback_conv:
                                st.error(f"Critical filter opt conv err for '{selected_column}': {e_fallback_conv}")

                    multiselect_label = f"Values for '{selected_column}' (by count):"

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
                        f"Column '{selected_column}' not found for filtering. It might have been removed or changed."
                    )

            if st.sidebar.button(f"Remove Filter {i+1}", key=f"remove_filter_votes_{filter_id}"):
                filters_to_remove_votes.append(i)

        if filters_to_remove_votes:
            for index in sorted(filters_to_remove_votes, reverse=True):
                del st.session_state.active_filters_votes[index]
            st.rerun()

        st.sidebar.markdown("---")
        col1_sidebar, col2_sidebar = st.sidebar.columns(2)
        apply_filters_button_votes = col1_sidebar.button("Apply Filters", key="apply_filters_btn_votes")
        reset_filters_button_votes = col2_sidebar.button("Reset Filters", key="reset_filters_btn_votes")

        if apply_filters_button_votes:
            temp_df = df_original.copy()
            filters_applied_count = 0
            try:
                for filt in st.session_state.active_filters_votes:
                    col = filt["column"]
                    vals = filt["values"]
                    if col != "None" and vals and col in temp_df.columns:  # Added check col in temp_df.columns
                        col_type = df_original[col].dtype
                        try:
                            if pd.api.types.is_numeric_dtype(col_type):
                                converted_vals = []
                                for v in vals:
                                    try:
                                        converted_vals.append(pd.to_numeric(v))
                                    except ValueError:
                                        st.warning(f"Could not convert '{v}' to number for '{col}'.")
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
                            st.warning(f"Filter error on '{col}' with '{vals}': {e_filter_type}. Using string match.")
                            temp_df = temp_df[temp_df[col].astype(str).isin(map(str, vals))]
                        filters_applied_count += 1
                    elif col not in temp_df.columns and col != "None":
                        st.warning(f"Filter column '{col}' not found. Skipping this filter.")

                st.session_state.filtered_df_votes = temp_df
                if filters_applied_count > 0:
                    st.sidebar.success(f"Applied {filters_applied_count} filter(s).")
                else:
                    st.sidebar.info("No active filters applied. Showing all data.")
                if filters_applied_count == 0:
                    st.session_state.filtered_df_votes = df_original  # Ensure reset if no filters actually applied
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error applying filters: {e}")

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
                st.sidebar.info("All filters reset. Showing all data.")
                st.rerun()
            else:
                st.sidebar.info("No filters to reset.")

        # --- Reset Database ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("Reset Database")
        st.sidebar.warning("This will delete the current database and start fresh. Please be sure before proceeding.")

        if st.sidebar.button("Reset Database", key="reset_db_btn"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.session_state.clear()
            st.success("Database reset. Data will be reloaded. Please rerun if needed.")
            st.rerun()

        st.header("Voters List")
        if st.session_state.filtered_df_votes is not None:
            if not st.session_state.filtered_df_votes.empty:
                total_in_filtered = len(st.session_state.filtered_df_votes)
                if "voted" in st.session_state.filtered_df_votes.columns:
                    voted_in_filtered = st.session_state.filtered_df_votes["voted"].astype(bool).sum()
                    col1_count, col2_count = st.columns(2)
                    with col1_count:
                        st.metric(label="Voted (Filtered View)", value=voted_in_filtered)
                    with col2_count:
                        st.metric(label="Total (Filtered View)", value=total_in_filtered)
                    st.markdown("---")
                else:
                    st.warning("The 'voted' column is missing, cannot display vote count.")
            else:
                st.info("No voters in the current filtered view to count.")

            df_display = st.session_state.filtered_df_votes.copy()
            if "voted" in df_display.columns:  # Ensure 'voted' column exists before trying to astype
                df_display["voted"] = df_display["voted"].astype(bool)
            else:
                st.error("Critical: 'voted' column is missing from display data. Cannot proceed with editing.")
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

            if not edited_df.equals(st.session_state.filtered_df_votes):
                # Merge on our new unique ID: voter_id (stored in st.session_state.id_column_name)
                comparison_df = st.session_state.filtered_df_votes.merge(
                    edited_df,
                    on=st.session_state.id_column_name,
                    suffixes=("_orig", "_edited"),
                    how="inner",
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
                            st.warning(f"Failed to update vote status for App ID {person_app_id} in DB.")
                    if updated_ids_count > 0:
                        st.success(f"Vote status updated for {updated_ids_count} voter(s) in the database.")
                        st.session_state.df_votes = load_data_from_db()
                        if st.session_state.df_votes is None:
                            st.error("Failed to reload data from DB after update. Critical error.")
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
                                        col_reapply != "None"
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
                                            st.error(f"Error re-applying filter on '{col_reapply}': {e_reapply}")
                            st.session_state.filtered_df_votes = temp_df_after_update
                            st.rerun()
                # This elif was for other changes, which should not happen if only 'voted' is editable.
                # elif not changed_rows.empty:
                #    st.session_state.filtered_df_votes = edited_df.copy()
                #    st.rerun()

            st.write(f"Displaying {len(edited_df)} voter(s).")
        else:
            st.info("No data to display. You might need to reset the database or check the Excel file.")
    # This else corresponds to if df_votes became None due to missing voter_id
    elif st.session_state.df_votes is None and "voter_id" in st.session_state.get("id_column_name", ""):
        st.warning(
            "Voter data is not available. Please use the 'Reset Database' button if the issue persists after a rerun."
        )


elif st.session_state.get("df_votes") is None and os.path.exists(DB_FILE):
    st.warning("Failed to load data from the existing database. Try resetting the database.")
elif not os.path.exists(EXCEL_FILE):
    st.error(f"Source Excel file '{EXCEL_FILE}' not found. Cannot initialize the database.")
else:
    st.info("DB initializing or issue occurred. Wait/refresh. Reset if persists.")
