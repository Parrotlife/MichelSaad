import pandas as pd


def load_data(file_path: str) -> pd.DataFrame | None:
    """
    Loads data from an Excel file into a pandas DataFrame.

    Args:
        file_path: The path to the Excel file.

    Returns:
        A pandas DataFrame containing the loaded data, or None if an error occurs.
    """
    try:
        df = pd.read_excel(file_path)
        print(f"Successfully loaded data from: {file_path}")
        return df
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during loading: {e}")

        return None


def filter_by_column(df: pd.DataFrame, column_name: str, values: list[str] | str) -> pd.DataFrame:
    """Filters the DataFrame based on whether a column's value is in the provided list."""
    if not isinstance(values, list):
        values = [values]  # Ensure values is always a list for consistent filtering
    # Convert DataFrame column to string to handle potential mixed types during comparison
    return df[df[column_name].astype(str).isin([str(v) for v in values])]


def summarize_by_column(df: pd.DataFrame, column_name: str | list[str]) -> pd.DataFrame:
    """
    Generates a summary DataFrame by grouping by one or more columns and counting occurrences.

    Args:
        df: The input DataFrame.
        column_name: The name of the column(s) to group by. Can be a single string or a list of strings.

    Returns:
        A summary DataFrame with counts per group.
    """
    # Convert single column to list for consistent handling
    columns = [column_name] if isinstance(column_name, str) else column_name

    # Verify all columns exist in the DataFrame
    missing_columns = [col for col in columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Column(s) {missing_columns} not found in DataFrame.")
        print(f"Available columns: {df.columns.tolist()}")
        return pd.DataFrame()  # Return empty DataFrame

    # Group by the specified column(s), count occurrences
    summary_df = df.groupby(columns).size().reset_index(name="count")  # type: ignore

    # Sort by count descending
    summary_df = summary_df.sort_values(by="count", ascending=False)

    # reset the index
    summary_df = summary_df.reset_index()

    # drop the count column
    summary_df = summary_df.drop(columns=["index"])

    return summary_df


def summarize_by_gender(df: pd.DataFrame) -> pd.DataFrame:
    """Summarizes data by gender ('الجنس')."""
    return summarize_by_column(df, "الجنس")


def summarize_by_religion(df: pd.DataFrame) -> pd.DataFrame:
    """Summarizes data by personal religion ('مذهب الشخصي')."""
    return summarize_by_column(df, "مذهب الشخصي")


def summarize_by_family_name(df: pd.DataFrame) -> pd.DataFrame:
    """Summarizes data by family name ('الشهرة')."""
    return summarize_by_column(df, "الشهرة")


def summarize_by_registry(df: pd.DataFrame) -> pd.DataFrame:
    """Summarizes data by registry number ('رقم السجل')."""
    return summarize_by_column(df, "رقم السجل")
