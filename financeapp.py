import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from rapidfuzz import fuzz

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Finance App", page_icon="💰", layout="wide")

category_file = "categories.json"

# ✅ PREDEFINED CATEGORIES
DEFAULT_CATEGORIES = {
    "Transportation": [],
    "Groceries": [],
    "Delivery": [],
    "Health": [],
    "Internet": [],
    "Dining": [],
    "Stuff": [],
    "Laundry": [],
    "Entertainment": [],
    "Uncategorized": []
}

# High-confidence rules
priority_rules = {
    "uber": "Transportation",
    "talabat": "Delivery",
    "snoonu": "Delivery",
    "carrefour": "Groceries",
    "lulu": "Groceries",
    "megamart": "Groceries",
    "ooredoo": "Internet",
    "cafe": "Dining",
    "coffee": "Dining",
    "restaurant": "Dining",
    "adidas": "Stuff",
    "sephora": "Stuff",
    "zara": "Stuff",
    "ikea": "Stuff",
    "cinema": "Entertainment",
}

# ---------------- SESSION ----------------
if "categories" not in st.session_state:
    st.session_state.categories = DEFAULT_CATEGORIES.copy()

# Load saved categories and merge safely
if os.path.exists(category_file):
    try:
        with open(category_file, "r") as f:
            saved = json.load(f)

            # Merge with defaults (ensures all categories exist)
            for cat in DEFAULT_CATEGORIES:
                if cat not in saved:
                    saved[cat] = []

            st.session_state.categories = saved
    except:
        pass


def save_categories():
    try:
        with open(category_file, "w") as f:
            json.dump(st.session_state.categories, f)
    except Exception as e:
        st.error(f"Could not save categories: {e}")


# ---------------- VENDOR EXTRACTION ----------------
def extract_vendor(text):
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)

    words = text.split()

    stopwords = {"payment", "debit", "credit", "pos", "txn", "purchase"}

    words = [w for w in words if w not in stopwords]

    return " ".join(words[:2])


# ---------------- CATEGORIZATION ----------------
def categorize_transactions(df):
    df["Category"] = "Uncategorized"

    for i, row in df.iterrows():
        text = str(row["Details"]).lower()

        # 1️⃣ Priority rules
        matched = False
        for key, cat in priority_rules.items():
            if key in text:
                df.at[i, "Category"] = cat
                matched = True
                break

        if matched:
            continue

        # 2️⃣ Fuzzy matching
        best_score = 0
        best_category = "Uncategorized"

        for category, keywords in st.session_state.categories.items():
            if category == "Uncategorized":
                continue

            for keyword in keywords:
                score = fuzz.partial_ratio(keyword, text)

                if score > best_score and score > 80:
                    best_score = score
                    best_category = category

        df.at[i, "Category"] = best_category

    return df


# ---------------- LOAD DATA ----------------
def load_transactions(file):
    try:
        try:
            df = pd.read_csv(file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin-1")

        df.columns = df.columns.str.strip()

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

        df["Category"] = "Uncategorized"
        df["Month"] = df["Date"].dt.to_period("M").astype(str)

        return categorize_transactions(df)

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None


# ---------------- LEARNING ----------------
def add_keyword_to_category(category, description, amount):
    if amount >= 0:
        return False

    vendor = extract_vendor(description)

    if vendor and vendor not in st.session_state.categories.get(category, []):
        st.session_state.categories[category].append(vendor)
        save_categories()
        return True

    return False


# ---------------- MAIN ----------------
def main():
    st.title("💰 Finance Dashboard")

    uploaded_file = st.file_uploader("Upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)

        if df is not None:

            expenses_df = df[df["Amount"] < 0].copy().reset_index(drop=True)
            refunds_df = df[df["Amount"] > 0].copy().reset_index(drop=True)

            st.session_state.expenses_df = expenses_df

            tab1, tab2 = st.tabs(["📉 Expenses", "💵 Refunds"])

            # ================= EXPENSES =================
            with tab1:

                st.caption("💡 Smart categorization with predefined categories")

                # -------- MONTH FILTER --------
                months = sorted(expenses_df["Month"].unique())
                selected_month = st.selectbox("Select Month", ["All"] + list(months))

                if selected_month != "All":
                    filtered_df = expenses_df[expenses_df["Month"] == selected_month]
                else:
                    filtered_df = expenses_df

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

                # -------- APPLY CHANGES --------
                if st.button("Apply Changes"):
                    learned = 0

                    for idx, row in edited_df.iterrows():
                        original_idx = filtered_df.index[idx]
                        old_cat = expenses_df.at[original_idx, "Category"]
                        new_cat = row["Category"]

                        if old_cat != new_cat:
                            expenses_df.at[original_idx, "Category"] = new_cat

                            if add_keyword_to_category(new_cat, row["Details"], row["Amount"]):
                                learned += 1

                    st.session_state.expenses_df = expenses_df

                    st.success(f"Changes applied. Learned {learned} vendor patterns.")

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

            # ================= REFUNDS =================
            with tab2:
                st.subheader("Refunds")

                total_refunds = refunds_df["Amount"].sum()

                st.metric("Total Refunds", f"{total_refunds:,.2f} QAR")

                st.dataframe(refunds_df, use_container_width=True)


main()
