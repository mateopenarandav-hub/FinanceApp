import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Finance App", page_icon="💰", layout="wide")

category_file = "categories.json"

# ---------------- SESSION ----------------
if "categories" not in st.session_state:
    st.session_state.categories = {"Uncategorized": []}

# Load saved categories
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


# ---------------- KEYWORD EXTRACTION ----------------
def extract_keywords(text):
    text = text.lower()

    # Remove numbers and symbols
    text = re.sub(r"[^a-z\s]", " ", text)

    words = text.split()

    # Common useless words to ignore
    stopwords = {
        "the", "and", "to", "for", "of", "in", "on", "at",
        "pos", "txn", "card", "payment", "debit", "credit"
    }

    keywords = [w for w in words if len(w) > 3 and w not in stopwords]

    return list(set(keywords))  # unique words


# ---------------- CATEGORIZATION ----------------
def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized":
            continue

        for keyword in keywords:
            keyword = keyword.lower().strip()

            mask = df["Details"].astype(str).str.lower().str.contains(
                rf"\b{keyword}\b", na=False
            )
            df.loc[mask, "Category"] = category

    return df


# ---------------- LOAD DATA ----------------
def load_transactions(file):
    try:
        # Encoding fallback
        try:
            df = pd.read_csv(file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin-1")

        df.columns = df.columns.str.strip()

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

        df["Category"] = "Uncategorized"

        # Add Month column
        df["Month"] = df["Date"].dt.to_period("M").astype(str)

        return categorize_transactions(df)

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None


# ---------------- SMART LEARNING ----------------
def add_keyword_to_category(category, description):
    keywords = extract_keywords(description)

    added = False

    for keyword in keywords:
        if keyword not in st.session_state.categories.get(category, []):
            st.session_state.categories[category].append(keyword)
            added = True

    if added:
        save_categories()

    return added


# ---------------- MAIN ----------------
def main():
    st.title("💰 Finance Dashboard")

    uploaded_file = st.file_uploader("Upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)

        if df is not None:

            # Split data
            expenses_df = df[df["Amount"] < 0].copy().reset_index(drop=True)
            refunds_df = df[df["Amount"] > 0].copy().reset_index(drop=True)

            st.session_state.expenses_df = expenses_df

            tab1, tab2 = st.tabs(["📉 Expenses", "💵 Refunds"])

            # ================= EXPENSES TAB =================
            with tab1:

                st.caption("💡 Categories are auto-predicted and improve over time")

                # -------- MONTH FILTER --------
                months = sorted(expenses_df["Month"].unique())
                selected_month = st.selectbox("Select Month", ["All"] + list(months))

                if selected_month != "All":
                    filtered_df = expenses_df[expenses_df["Month"] == selected_month]
                else:
                    filtered_df = expenses_df

                # -------- CATEGORY MANAGEMENT --------
                new_category = st.text_input("New Category Name")
                if st.button("Add Category"):
                    if new_category and new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.rerun()

                # -------- TABLE --------
                st.subheader("Expenses")

                edited_df = st.data_editor(
                    filtered_df[["Date", "Details", "Amount", "Category"]],
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

                # Save edits + LEARNING
                if st.button("Apply Changes"):
                    for idx, row in edited_df.iterrows():
                        original_idx = filtered_df.index[idx]
                        old_cat = expenses_df.at[original_idx, "Category"]
                        new_cat = row["Category"]

                        if old_cat != new_cat:
                            expenses_df.at[original_idx, "Category"] = new_cat

                            # 🔥 Learn from correction
                            add_keyword_to_category(new_cat, row["Details"])

                    st.session_state.expenses_df = expenses_df
                    st.success("Changes applied and system learned new patterns!")

                # -------- SUMMARY --------
                st.subheader("Expense Summary")

                category_totals = (
                    filtered_df
                    .groupby("Category")["Amount"]
                    .sum()
                    .abs()
                    .reset_index()
                    .sort_values("Amount", ascending=False)
                )

                st.dataframe(category_totals, use_container_width=True, hide_index=True)

                fig_pie = px.pie(
                    category_totals,
                    values="Amount",
                    names="Category",
                    title="Expenses by Category"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

                # -------- MONTHLY TREND --------
                st.subheader("Monthly Trend")

                monthly_totals = (
                    expenses_df
                    .groupby("Month")["Amount"]
                    .sum()
                    .abs()
                    .reset_index()
                    .sort_values("Month")
                )

                fig_month = px.bar(
                    monthly_totals,
                    x="Month",
                    y="Amount",
                    title="Monthly Expenses",
                    text="Amount"
                )

                fig_month.update_traces(texttemplate='%{text:.2s}', textposition='outside')
                fig_month.update_layout(xaxis_title="Month", yaxis_title="Amount (QAR)")

                st.plotly_chart(fig_month, use_container_width=True)

                # -------- CATEGORY vs MONTH --------
                st.subheader("Category vs Month")

                monthly_category = (
                    expenses_df
                    .groupby(["Month", "Category"])["Amount"]
                    .sum()
                    .abs()
                    .reset_index()
                )

                fig_bar = px.bar(
                    monthly_category,
                    x="Month",
                    y="Amount",
                    color="Category",
                    title="Expenses by Category per Month"
                )

                st.plotly_chart(fig_bar, use_container_width=True)

                # -------- PIVOT TABLE --------
                st.subheader("Detailed Table (Category x Month)")

                pivot_table = (
                    expenses_df
                    .groupby(["Month", "Category"])["Amount"]
                    .sum()
                    .abs()
                    .reset_index()
                )

                pivot_table = pivot_table.pivot(
                    index="Category",
                    columns="Month",
                    values="Amount"
                ).fillna(0)

                st.dataframe(pivot_table, use_container_width=True)

            # ================= REFUNDS TAB =================
            with tab2:
                st.subheader("Refunds")

                total_refunds = refunds_df["Amount"].sum()

                st.metric("Total Refunds", f"{total_refunds:,.2f} QAR")

                st.dataframe(refunds_df, use_container_width=True)


main()
