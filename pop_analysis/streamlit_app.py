# Assuming data_analyzer.py is in the same directory or Python path
import data_analyzer as da
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")

st.title("Excel Data Analyzer")

# --- Initialize session state ---
# Persists variables across reruns
if "df" not in st.session_state:
    st.session_state.df = None  # Stores the original DataFrame
if "filtered_df" not in st.session_state:
    st.session_state.filtered_df = None  # Stores the filtered (or original) DataFrame for display/analysis
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None  # Tracks the name of the uploaded file
if "active_filters" not in st.session_state:
    st.session_state.active_filters = (
        []
    )  # List to store filter dicts: {'id': unique_id, 'column': col, 'values': [vals]}

# --- File Upload ---
# Place the uploader at the top
uploaded_file = st.file_uploader("Choose an Excel file (.xlsx)", type="xlsx")

# --- Load Data ---
# This block executes when a file is uploaded
if uploaded_file is not None:
    # Load data only if it's a new file or not loaded yet
    if st.session_state.df is None or st.session_state.uploaded_filename != uploaded_file.name:
        try:
            # Use pandas directly to read the uploaded file object
            df = pd.read_excel(uploaded_file)
            st.session_state.df = df
            st.session_state.filtered_df = df  # Initialize filtered_df with the full df
            st.session_state.uploaded_filename = uploaded_file.name
            st.success(f"Successfully loaded '{uploaded_file.name}'")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            # Reset state on loading error
            st.session_state.df = None
            st.session_state.filtered_df = None
            st.session_state.uploaded_filename = None
            st.stop()  # Stop script execution if file loading fails

# --- Main App Logic (only runs if data is successfully loaded) ---
if st.session_state.df is not None:
    df = st.session_state.df  # Get the original dataframe
    columns = df.columns.tolist()  # Get column names for UI widgets

    st.sidebar.header("Analysis Options")

    # --- Filtering Section ---
    st.sidebar.subheader("Filter Data")

    # Button to add a new filter criteria
    if st.sidebar.button("Add Filter", key="add_filter_btn"):
        # Add a new filter definition with a unique ID
        new_filter_id = pd.Timestamp.now().strftime("%Y%m%d%H%M%S%f")  # Simple unique ID
        st.session_state.active_filters.append({"id": new_filter_id, "column": "None", "values": []})
        st.rerun()

    # Display UI for each active filter
    filters_to_remove = []
    for i, filt in enumerate(st.session_state.active_filters):
        filter_id = filt["id"]
        st.sidebar.markdown("***")  # Separator

        cols_with_none = ["None"] + columns
        selected_column = st.sidebar.selectbox(
            "Filter by column:",
            cols_with_none,
            index=cols_with_none.index(filt["column"]) if filt["column"] in cols_with_none else 0,
            key=f"filter_col_select_{filter_id}",
        )

        # Update the column in the session state immediately if changed
        if selected_column != filt["column"]:
            st.session_state.active_filters[i]["column"] = selected_column
            st.session_state.active_filters[i]["values"] = []  # Reset values when column changes
            st.rerun()  # Rerun to update value options

        selected_values = []
        if selected_column != "None":
            # Calculate value counts and sort unique values by frequency
            if selected_column in df.columns:
                value_counts = df[selected_column].value_counts()
                sorted_unique_values = value_counts.index.tolist()

                if sorted_unique_values:
                    try:
                        display_values = [str(v) for v in sorted_unique_values]
                    except TypeError:
                        unique_values_fallback = df[selected_column].unique()
                        display_values = [str(v) for v in unique_values_fallback]

                    selected_values = st.sidebar.multiselect(
                        f"Select value(s) for '{selected_column}' (ordered by count):",
                        options=display_values,
                        default=filt["values"],  # Use stored values as default
                        key=f"filter_val_multiselect_{filter_id}",
                    )
                    # Update the values in the session state immediately if changed
                    if selected_values != filt["values"]:
                        st.session_state.active_filters[i]["values"] = selected_values
                        # No rerun here needed, apply button will handle it
                else:
                    st.sidebar.info(f"Column '{selected_column}' has no values to select.")
            else:
                st.sidebar.error(f"Column '{selected_column}' not found.")  # Should not happen

        # Button to remove this specific filter
        if st.sidebar.button(f"Remove Filter {i+1}", key=f"remove_filter_{filter_id}"):
            filters_to_remove.append(i)

    # Remove filters marked for removal (iterate in reverse to avoid index issues)
    if filters_to_remove:
        for index in sorted(filters_to_remove, reverse=True):
            del st.session_state.active_filters[index]
        st.rerun()

    st.sidebar.markdown("***")  # Separator
    # Consolidated Apply/Reset Button
    col1, col2 = st.sidebar.columns(2)
    apply_filters_button = col1.button("Apply All Filters", key="apply_all_filters_btn")
    reset_filters_button = col2.button("Reset All Filters", key="reset_all_filters_btn")

    # --- Apply / Reset Logic --- #
    # This logic needs to be updated to handle the new structure
    if apply_filters_button:
        temp_df = df.copy()
        filters_applied_count = 0
        try:
            for filt in st.session_state.active_filters:
                col = filt["column"]
                vals = filt["values"]
                if col != "None" and vals:
                    temp_df = da.filter_by_column(temp_df, col, vals)
                    filters_applied_count += 1

            st.session_state.filtered_df = temp_df
            if filters_applied_count > 0:
                st.sidebar.success(f"Applied {filters_applied_count} filter(s).")
            else:
                st.sidebar.info("No active filters to apply. Showing all data.")
                # Ensure filtered_df is reset if no filters were applied but it wasn't the original
                if st.session_state.filtered_df is not df:
                    st.session_state.filtered_df = df
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error applying filters: {e}")

    if reset_filters_button:
        if st.session_state.active_filters or st.session_state.filtered_df is not df:
            st.session_state.active_filters = []
            st.session_state.filtered_df = df
            st.sidebar.info("All filters reset. Showing all data.")
            st.rerun()
        else:
            st.sidebar.info("No filters to reset.")

    # --- Summarization Section ---
    st.sidebar.subheader("Summarize Active Data")
    summarize_columns = st.sidebar.multiselect(
        "Group by column(s):", columns, key="summarize_cols"  # Use columns from the original df for selection options
    )
    summarize_button = st.sidebar.button("Generate Summary", key="summarize_btn")

    # --- Display Area ---
    st.header("Active Data")
    st.write("Data currently being analyzed (filtered or original).")
    # Always display the dataframe stored in st.session_state.filtered_df
    # Add a check to ensure filtered_df is not None before using it
    if st.session_state.filtered_df is not None:
        active_df = st.session_state.filtered_df
        st.dataframe(active_df)
        st.write(f"Showing {len(active_df)} rows.")  # Safe now as active_df is not None

        # --- Display Summary Results ---
        # This block executes when the summarize button is clicked
        if summarize_button:
            if summarize_columns:
                try:
                    # Use the *currently active* dataframe (active_df) for summarization
                    # active_df is guaranteed not None here
                    summary_df = da.summarize_by_column(active_df, summarize_columns)

                    st.header("Summary Statistics")
                    if not summary_df.empty:
                        st.dataframe(summary_df)
                        # --- Add Pie Chart ---
                        try:
                            # Check if summary_df is suitable for bar chart
                            # Assumes index is the category and 'count' (or other numeric cols) are values
                            # We might need more sophisticated logic if there are multiple numeric columns
                            # or if the index needs to be set explicitly for charting.
                            # Let's assume the index from reset_index() is what we want on x-axis
                            # and 'count' is the y-axis for now.
                            # If summarize_columns has multiple items, the index might be a MultiIndex.
                            # `st.bar_chart` might handle MultiIndex well, or we might need to prepare data.
                            # Let's try plotting 'count' against the group columns (index).

                            chart_df = summary_df.copy()

                            # If multiple grouping columns, create a single string representation for the x-axis label
                            if isinstance(summarize_columns, list) and len(summarize_columns) > 1:
                                # Combine index columns into a single string column for plotting
                                index_col_name = "_".join(summarize_columns)
                                chart_df[index_col_name] = chart_df[summarize_columns].apply(
                                    lambda row: " - ".join(row.astype(str)), axis=1
                                )
                                chart_df = chart_df.set_index(index_col_name)
                            else:
                                # If single grouping column, use it as index
                                index_col = (
                                    summarize_columns[0] if isinstance(summarize_columns, list) else summarize_columns
                                )
                                chart_df = chart_df.set_index(index_col)

                            # Select only the 'count' column for the bar chart values
                            if "count" in chart_df.columns:
                                # st.bar_chart(chart_df[['count']]) # Removed bar chart
                                # --- Add Pie Chart --- #
                                st.subheader("Summary Distribution")
                                try:
                                    # Prepare title based on single or multiple columns
                                    if isinstance(summarize_columns, list):
                                        title_cols = ", ".join(summarize_columns)
                                    else:
                                        title_cols = summarize_columns
                                    chart_title = f"Distribution for {title_cols}"

                                    fig = px.pie(chart_df, values="count", names=chart_df.index, title=chart_title)
                                    st.plotly_chart(fig)
                                except Exception as pie_error:
                                    st.error(f"Could not generate pie chart: {pie_error}")
                            else:
                                st.warning("Summary data does not contain a 'count' column for charting.")

                        except Exception as chart_error:
                            st.error(f"Could not generate bar chart: {chart_error}")
                    # Check active_df.empty instead of st.session_state.filtered_df.empty
                    elif active_df.empty:
                        st.warning(
                            "Cannot generate summary or"
                            + " chart because the active data table is empty (due to filtering)."
                        )
                    else:
                        # This might happen if selected columns don't exist in the filtered_df (shouldn't happen here)
                        # or if summarize_by_column itself returns empty for valid reasons.
                        st.info("Summary generated successfully, but the result is empty.")

                except Exception as e:
                    st.error(f"An error occurred during summarization: {e}")
            else:
                # If button is clicked without selecting columns
                st.warning("Please select at least one column to group by for summarization.")
    else:
        # This case handles if filtered_df somehow became None after initial load
        st.warning("No active data to display. Try reloading the file.")

# --- Initial Prompt ---
# Show prompt only if no file has ever been successfully loaded in the session
elif st.session_state.uploaded_filename is None:
    st.info("☝️ Upload an Excel file (.xlsx) to begin analysis.")
