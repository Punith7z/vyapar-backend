import urllib.request
import json
import traceback

tests = [
    # 1-7: basic loose
    ("2 kg rice", "Rice", 2.0, "kg", None, False),
    ("rice 2 kg", "Rice", 2.0, "kg", None, False),
    ("5kg sugar", "Sugar", 5.0, "kg", None, False),
    ("2.5 kg potato", "Potato", 2.5, "kg", None, False),
    ("500g sugar", "Sugar", 500.0, "g", None, False),
    ("1 litre oil", "Oil", 1.0, "L", None, False),
    ("500ml milk", "Milk", 500.0, "ml", None, False),
    # 8-16: packaged
    ("10 packets Parle G", "Parle G", 10.0, "packet", None, False),
    ("20 bottles water 1L", "Water", 20.0, "bottle", "1 L", False),
    ("Aashirvaad Atta 5kg 10", "Aashirvaad Atta", 10.0, "packet", "5 kg", False),
    ("Aashirvaad Atta 5kg x 10", "Aashirvaad Atta", 10.0, "packet", "5 kg", False),
    ("Fortune Sunflower Oil 1L x 12", "Fortune Sunflower Oil", 12.0, "bottle", "1 L", False),
    ("Amul Taaza 500ml 20", "Amul Taaza", 20.0, "packet", "500 ml", False),
    ("Parle G 100g 24", "Parle G", 24.0, "packet", "100 g", False),
    ("7UP 500ML 24", "7Up", 24.0, "packet", "500 ml", False),
    ("5 Star 45g 24", "5 Star", 24.0, "packet", "45 g", False),
    # 17-18: pcs
    ("Eggs 30 pcs", "Eggs", 30.0, "pcs", None, False),
    ("Lux Soap 100g 24 pcs", "Lux Soap", 24.0, "pcs", "100 g", False),
    # 19: Price
    ("Rice 5kg 10 5000", "Rice", 10.0, "packet", "5 kg", False),
    # 22-23: Unclear
    ("Q Kg Rice", "Q Kg Rice", None, None, None, True),
    ("Rice ? kg", "Rice ? kg", None, None, None, True),
    # 25-28: Natural language
    ("add 2 kg rice", "Rice", 2.0, "kg", None, False),
    ("bought 5 packets parle g", "Parle G", 5.0, "packet", None, False),
    ("10 bottles of 1 litre oil", "Oil", 10.0, "bottle", "1 L", False),
    ("20 packets biscuits 100 grams", "Biscuits", 20.0, "packet", "100 g", False)
]

def run_tests():
    all_passed = True
    for t in tests:
        input_str, exp_name, exp_qty, exp_unit, exp_pack, exp_review = t
        req = urllib.request.Request("http://localhost:8000/parse_bill", data=json.dumps({"ocrText": input_str}).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read().decode())
        except Exception as e:
            print(f"Error calling API for '{input_str}': {e}")
            all_passed = False
            continue
            
        items = res.get("items", [])
        if not items:
            print(f"FAIL: {input_str} -> returned no items")
            all_passed = False
            continue
            
        item = items[0]
        name = item.get("productName", "")
        qty = item.get("quantity")
        unit = item.get("unit")
        pack = item.get("packSize")
        review = item.get("needsReview", False)
        
        fail = False
        if name.lower() != exp_name.lower():
            print(f"FAIL NAME: {input_str} -> Expected '{exp_name}', got '{name}'")
            fail = True
        if qty != exp_qty:
            print(f"FAIL QTY: {input_str} -> Expected {exp_qty}, got {qty}")
            fail = True
        if (unit or "").lower() != (exp_unit or "").lower():
            print(f"FAIL UNIT: {input_str} -> Expected {exp_unit}, got {unit}")
            fail = True
        if (pack or "").lower().replace('l', 'l') != (exp_pack or "").lower().replace('l', 'l'):
            print(f"FAIL PACK: {input_str} -> Expected {exp_pack}, got {pack}")
            fail = True
        if review != exp_review:
            print(f"FAIL REVIEW: {input_str} -> Expected {exp_review}, got {review}")
            fail = True
            
        if fail:
            all_passed = False
        else:
            print(f"PASS: {input_str}")
            
    # Test exclusions
    exclusions = ["CGST 2.5%", "SGST 2.5%", "TOTAL 5000", "Invoice No 12345", "Date 10/09/2026", "GSTIN XXXXX", "THANK YOU", "GST"]
    for x in exclusions:
        req = urllib.request.Request("http://localhost:8000/parse_bill", data=json.dumps({"ocrText": x}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            if res.get("items"):
                print(f"FAIL EXCLUSION: '{x}' returned items {res['items']}")
                all_passed = False
            else:
                print(f"PASS EXCLUSION: {x}")
                
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED.")

if __name__ == "__main__":
    run_tests()
