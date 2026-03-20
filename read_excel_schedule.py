#!/usr/bin/env python
"""Read and analyze Excel schedule file"""

import pandas as pd
import sys
import io

# Read Excel file
excel_path = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\Копия 1 курс Расписание 2 семестр.xlsx"

# Get sheet names
xl = pd.ExcelFile(excel_path)
print(f"Sheets: {xl.sheet_names}")

# Read first sheet
df = pd.read_excel(excel_path, sheet_name=0, header=None)
print(f"Shape: {df.shape}")

# Save to CSV for analysis
output_csv = r"C:\Users\tkulz\Downloads\college_schedule_backup_20251212\college_schedule\schedule_analysis.csv"
df.to_csv(output_csv, encoding='utf-8', index=True)
print(f"Saved to: {output_csv}")

# Print basic info
print("\nColumn 0 (days/pairs):")
for i, val in enumerate(df.iloc[:30, 0].values):
    print(f"  Row {i}: {repr(val)}")

print("\nRow 0 (groups header):")
for i, val in enumerate(df.iloc[0, :20].values):
    print(f"  Col {i}: {repr(val)}")

print("\nRow 1:")
for i, val in enumerate(df.iloc[1, :20].values):
    print(f"  Col {i}: {repr(val)}")

print("\nRow 2:")
for i, val in enumerate(df.iloc[2, :20].values):
    print(f"  Col {i}: {repr(val)}")
