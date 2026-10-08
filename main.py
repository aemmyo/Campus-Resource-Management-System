"""Campus Resource Management System (CLI) - Python standard library only."""

import copy
import json
import os

DATA_FILE = "campus_data.json"
LOW_STOCK_LIMIT = 3

SEED_RESOURCES = [
    {"id": "R001", "name": "Laptop", "category": "Electronics", "total": 10, "available": 10},
    {"id": "R002", "name": "Keyboard", "category": "Accessories", "total": 5, "available": 5},
    {"id": "R003", "name": "Headset", "category": "Accessories", "total": 3, "available": 3},
]
SEED_FELLOWS = {"F001": "Ada", "F002": "John", "F003": "Grace"}


# ---------------------------------------------------------------- state
def new_state():
    """Fresh state built from the starting data (deep-copied)."""
    return {
        "resources": copy.deepcopy(SEED_RESOURCES),
        "fellows": dict(SEED_FELLOWS),
        "borrow_records": [],  # each: {fellow_id, resource_id, quantity, returned}
    }


def save_state(state, path=DATA_FILE):
    """Persist inventory and loans to JSON (bonus)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        return True, f"Data saved to {path}."
    except OSError as err:
        return False, f"Could not save data: {err}"


def load_state(path=DATA_FILE):
    """Load state from JSON; fall back to starting data if missing/corrupt."""
    if not os.path.exists(path):
        return new_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("resources", "fellows", "borrow_records"):
            if key not in data:
                raise ValueError(f"missing '{key}'")
        return data
    except (OSError, ValueError) as err:
        print(f"Warning: could not load {path} ({err}). Using starting data.")
        return new_state()


# ---------------------------------------------------------------- helpers
def parse_positive_int(text):
    """Return int if text is a strictly positive whole number, else None."""
    text = str(text).strip()
    if text.isdigit() and int(text) > 0:
        return int(text)
    return None


def find_resource(state, resource_id):
    rid = str(resource_id).strip().upper()
    for res in state["resources"]:
        if res["id"].upper() == rid:
            return res
    return None


def normalise_fellow_id(state, fellow_id):
    fid = str(fellow_id).strip().upper()
    return fid if fid in state["fellows"] else None


def on_loan(state, fellow_id, resource_id):
    """Units of a resource a fellow currently has on loan."""
    return sum(
        r["quantity"] - r["returned"]
        for r in state["borrow_records"]
        if r["fellow_id"] == fellow_id and r["resource_id"] == resource_id
    )


# ---------------------------------------------------------------- 1. inventory
def add_resource(state, rid, name, category, total):
    rid, name, category = str(rid).strip().upper(), str(name).strip(), str(category).strip()
    if not rid or not name or not category:
        return False, "ID, name and category cannot be empty."
    if find_resource(state, rid):
        return False, f"Resource ID '{rid}' already exists."
    units = parse_positive_int(total)
    if units is None:
        return False, "Total units must be a positive whole number."
    state["resources"].append(
        {"id": rid, "name": name, "category": category, "total": units, "available": units}
    )
    return True, f"Added {name} ({rid}) with {units} units."


def format_resources(resources):
    if not resources:
        return "No resources found."
    lines = [f"{'ID':<8}{'Name':<20}{'Category':<16}{'Total':>6}{'Avail':>7}", "-" * 57]
    for r in resources:
        lines.append(f"{r['id']:<8}{r['name']:<20}{r['category']:<16}{r['total']:>6}{r['available']:>7}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 2. borrowing
def borrow(state, fellow_id, resource_id, quantity):
    """Validate everything first; mutate state only on full success."""
    fid = normalise_fellow_id(state, fellow_id)
    if fid is None:
        return False, f"Unknown fellow ID '{str(fellow_id).strip()}'."
    res = find_resource(state, resource_id)
    if res is None:
        return False, f"Unknown resource ID '{str(resource_id).strip()}'."
    qty = parse_positive_int(quantity)
    if qty is None:
        return False, "Quantity must be a positive whole number."
    if qty > res["available"]:
        return False, (f"Rejected: {state['fellows'][fid]} requested {qty} {res['name']}(s) "
                       f"but only {res['available']} available.")
    res["available"] -= qty
    state["borrow_records"].append(
        {"fellow_id": fid, "resource_id": res["id"], "quantity": qty, "returned": 0}
    )
    return True, (f"{state['fellows'][fid]} borrowed {qty} {res['name']}(s). "
                  f"Available now: {res['available']}.")


# ---------------------------------------------------------------- 3. returns
def return_item(state, fellow_id, resource_id, quantity):
    fid = normalise_fellow_id(state, fellow_id)
    if fid is None:
        return False, f"Unknown fellow ID '{str(fellow_id).strip()}'."
    res = find_resource(state, resource_id)
    if res is None:
        return False, f"Unknown resource ID '{str(resource_id).strip()}'."
    qty = parse_positive_int(quantity)
    if qty is None:
        return False, "Quantity must be a positive whole number."
    held = on_loan(state, fid, res["id"])
    if qty > held:
        return False, (f"Rejected: {state['fellows'][fid]} only has {held} "
                       f"{res['name']}(s) on loan, cannot return {qty}.")
    remaining = qty  # settle against oldest open loans first
    for rec in state["borrow_records"]:
        if remaining == 0:
            break
        if rec["fellow_id"] == fid and rec["resource_id"] == res["id"]:
            take = min(remaining, rec["quantity"] - rec["returned"])
            rec["returned"] += take
            remaining -= take
    res["available"] += qty
    return True, (f"{state['fellows'][fid]} returned {qty} {res['name']}(s). "
                  f"Available now: {res['available']}.")


# ---------------------------------------------------------------- 4. search/filter
def search_by_name(state, term):
    term = str(term).strip().lower()
    if not term:
        return []
    return [r for r in state["resources"] if term in r["name"].lower()]


def filter_by_category(state, category):
    category = str(category).strip().lower()
    return [r for r in state["resources"] if r["category"].lower() == category]


# ---------------------------------------------------------------- 5. reports
def build_report(state):
    resources = state["resources"]
    total = sum(r["total"] for r in resources)
    available = sum(r["available"] for r in resources)
    borrowed_by_res = {r["id"]: r["total"] - r["available"] for r in resources}
    borrowed = sum(borrowed_by_res.values())
    low = [r for r in resources if r["available"] < LOW_STOCK_LIMIT]
    top = max(borrowed_by_res.values(), default=0)
    leaders = [r for r in resources if top > 0 and borrowed_by_res[r["id"]] == top]
    return {"total": total, "available": available, "borrowed": borrowed,
            "low_stock": low, "top_borrowed": top, "leaders": leaders}


def format_report(state):
    rep = build_report(state)
    lines = ["=== INVENTORY REPORT ===",
             f"Total units:      {rep['total']}",
             f"Available units:  {rep['available']}",
             f"Borrowed units:   {rep['borrowed']}",
             f"Low stock (< {LOW_STOCK_LIMIT} available):"]
    if rep["low_stock"]:
        lines += [f"  - {r['name']} ({r['available']})" for r in rep["low_stock"]]
    else:
        lines.append("  None")
    if rep["leaders"]:
        label = "Most borrowed" if len(rep["leaders"]) == 1 else "Most borrowed (tie)"
        names = ", ".join(r["name"] for r in rep["leaders"])
        lines.append(f"{label}: {names} ({rep['top_borrowed']} units on loan)")
    else:
        lines.append("Most borrowed: none (nothing currently on loan)")
    return "\n".join(lines)


# ---------------------------------------------------------------- demo
def run_demo():
    """Required demonstration, in order, on a fresh in-memory state."""
    state = new_state()
    steps = [
        ("1. F001 borrows 2 laptops", lambda: borrow(state, "F001", "R001", 2)),
        ("2. F002 borrows 3 keyboards", lambda: borrow(state, "F002", "R002", 3)),
        ("3. F001 returns 1 laptop", lambda: return_item(state, "F001", "R001", 1)),
        ("4. F003 requests 4 headsets", lambda: borrow(state, "F003", "R003", 4)),
        ("5. F002 tries to return 4 keyboards", lambda: return_item(state, "F002", "R002", 4)),
    ]
    for title, action in steps:
        ok, msg = action()
        print(f"\n{title}\n   [{'OK' if ok else 'REJECTED'}] {msg}")
    print("\n6. Search for 'LAPtop'")
    print(format_resources(search_by_name(state, "LAPtop")))
    print("\n7. Report")
    print(format_report(state))


# ---------------------------------------------------------------- menu
MENU = """
===== Campus Resource Management =====
1. Add resource
2. List resources
3. Borrow
4. Return
5. Search by name
6. Filter by category
7. Report
8. Run required demonstration
9. Save data
0. Exit
"""


def ask(prompt):
    return input(prompt).strip()


def main():
    state = load_state()
    while True:
        print(MENU)
        choice = ask("Choose an option: ")
        if choice == "1":
            print(add_resource(state, ask("ID: "), ask("Name: "), ask("Category: "), ask("Total units: "))[1])
        elif choice == "2":
            print(format_resources(state["resources"]))
        elif choice == "3":
            print(borrow(state, ask("Fellow ID: "), ask("Resource ID: "), ask("Quantity: "))[1])
        elif choice == "4":
            print(return_item(state, ask("Fellow ID: "), ask("Resource ID: "), ask("Quantity: "))[1])
        elif choice == "5":
            results = search_by_name(state, ask("Name to search: "))
            print(format_resources(results))
        elif choice == "6":
            print(format_resources(filter_by_category(state, ask("Category: "))))
        elif choice == "7":
            print(format_report(state))
        elif choice == "8":
            run_demo()
        elif choice == "9":
            print(save_state(state)[1])
        elif choice == "0":
            print(save_state(state)[1])
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please enter a number from the menu (0-9).")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")