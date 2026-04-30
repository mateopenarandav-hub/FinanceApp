import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# MUST be first Streamlit command
st.set_page_config(page_title="Finance App", page_icon="💰", layout="wide")

category_file = "categories.json"

# ---------------- SESSION STATE ----------------
if "categories" not in st.session_state:
    st.session_state.categories = {"Uncategorized": []}

# ---------------- LOAD SAVED CATEGORIES ----------------
if os.path.exists(category_file):
    try:
        with open(category_file, "r") as f:
            st.session_state.categories = json.load(f)
    except:
        pass


def save_categories():
    try:
        with open(category_file, "w") as f:
            json.dump(st.session_state.categories, f)
    except Exception as e:
        st.error(f"Could not save categories: {e}")


# ---------------- CATEGORIZATION ----------------
def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized":
            continue

        for keyword in keywords:
            keyword = keyword.lower().strip()

            mask = df["Details"].astype(str).str.lower().str.contains(keyword, na=False)
            df.loc[mask, "Category"] = category

    return df


# ---------------- LOAD DATA ----------------
def load_transactions(file):
    try:
        df = pd.read_csv(file)
        df.columns = df.columns.str.strip()

        # Amount cleanup
        df["Amount"] = pd.to_numeric(
            df["Amount"].astype(str).str.replace(",", ""),
            errors="coerce"
        )

        # Date cleanup (your format is DD/MM/YYYY)
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

        # Ensure required column exists
        df["Category"] = "Uncategorized"

        return categorize_transactions(df)

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None


# ---------------- ADD KEYWORDS ----------------
def add_keyword_to_category(category, keyword):
    keyword = keyword.strip()

    if keyword and keyword not in st.session_state.categories.get(category, []):
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True

    return False


# ---------------- MAIN APP ----------------
def main():
    st.title("💰 Finance Dashboard")

    uploaded_file = st.file_uploader("Upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)

        if df is not None:

            # ---------------- SPLIT DATA ----------------
            expenses_df = df[df["Amount"] < 0].copy().reset_index(drop=True)
            refunds_df = df[df["Amount"] > 0].copy().reset_index(drop=True)

            st.session_state.expenses_df = expenses_df

            # ---------------- TABS ----------------
            tab1, tab2 = st.tabs(["📉 Expenses", "💵 Refunds"])

            # ================= EXPENSES TAB =================
            with tab1:
                st.subheader("Expenses")

                # Add new category
                new_category = st.text_input("New Category Name")
                if st.button("Add Category"):
                    if new_category and new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.rerun()

                # Editable table
                edited_df = st.data_editor(
                    st.session_state.expenses_df[["Date", "Details", "Amount", "Category"]],
                    column_config={
                        "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                        "Amount": st.column_config.NumberColumn("Amount", format="%.2f QAR"),
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            options=list(st.session_state.categories.keys())
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="expense_editor"
                )

                # Save edits
                if st.button("Apply Changes"):
                    for idx, row in edited_df.iterrows():
                        old_cat = st.session_state.expenses_df.at[idx, "Category"]
                        new_cat = row["Category"]

                        if old_cat != new_cat:
                            st.session_state.expenses_df.at[idx, "Category"] = new_cat
                            add_keyword_to_category(new_cat, row["Details"])

                # ---------------- SUMMARY ----------------
                st.subheader("Expense Summary")

                category_totals = (
                    st.session_state.expenses_df
                    .groupby("Category")["Amount"]
                    .sum()
                    .abs()
                    .reset_index()
                    .sort_values("Amount", ascending=False)
                )

                st.dataframe(category_totals, use_container_width=True, hide_index=True)

                fig = px.pie(
                    category_totals,
                    values="Amount",
                    names="Category",
                    title="Expenses by Category"
                )

                st.plotly_chart(fig, use_container_width=True)

            # ================= REFUNDS TAB =================
            with tab2:
                st.subheader("Refunds")

                total_refunds = refunds_df["Amount"].sum()

                st.metric("Total Refunds", f"{total_refunds:,.2f} QAR")

                st.dataframe(refunds_df, use_container_width=True)


main()
