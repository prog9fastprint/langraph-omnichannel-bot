import csv
from io import StringIO
import re

text = ",Fast Print Indonesia,Uncategorized,Sparepart Printer,CAT_SPARE_PART, promo"
rows = list(csv.reader(StringIO(text)))
print("With comma:")
print(f"fields[0] = {rows[0][0]}")
print(f"fields[1] = {rows[0][1]}")

text2 = "Fast Print Indonesia,Uncategorized,Sparepart Printer,CAT_SPARE_PART, promo"
rows2 = list(csv.reader(StringIO(text2)))
print("\nWithout comma:")
print(f"fields[0] = {rows2[0][0]}")
print(f"fields[1] = {rows2[0][1]}")
