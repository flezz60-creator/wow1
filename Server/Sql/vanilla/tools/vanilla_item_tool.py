#!/usr/bin/env python3
"""Utility CLI to help create Vanilla (1.12) item templates and assign drops.

The tool keeps an on-disk JSON store next to the script. It allows creating
custom items for the `item_template` table, assigning them to bosses via the
`creature_loot_template` table and exporting ready-to-run SQL statements.
"""

from __future__ import annotations

import argparse
import configparser
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

STORE_PATH = Path(__file__).with_name("vanilla_item_store.json")


@dataclass
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


ITEM_TEMPLATE_COLUMNS: Tuple[str, ...] = (
    "entry",
    "class",
    "subclass",
    "name",
    "displayid",
    "Quality",
    "Flags",
    "BuyCount",
    "BuyPrice",
    "SellPrice",
    "InventoryType",
    "AllowableClass",
    "AllowableRace",
    "ItemLevel",
    "RequiredLevel",
    "RequiredSkill",
    "RequiredSkillRank",
    "requiredspell",
    "requiredhonorrank",
    "RequiredCityRank",
    "RequiredReputationFaction",
    "RequiredReputationRank",
    "maxcount",
    "stackable",
    "ContainerSlots",
    "stat_type1",
    "stat_value1",
    "stat_type2",
    "stat_value2",
    "stat_type3",
    "stat_value3",
    "stat_type4",
    "stat_value4",
    "stat_type5",
    "stat_value5",
    "stat_type6",
    "stat_value6",
    "stat_type7",
    "stat_value7",
    "stat_type8",
    "stat_value8",
    "stat_type9",
    "stat_value9",
    "stat_type10",
    "stat_value10",
    "dmg_min1",
    "dmg_max1",
    "dmg_type1",
    "dmg_min2",
    "dmg_max2",
    "dmg_type2",
    "dmg_min3",
    "dmg_max3",
    "dmg_type3",
    "dmg_min4",
    "dmg_max4",
    "dmg_type4",
    "dmg_min5",
    "dmg_max5",
    "dmg_type5",
    "armor",
    "holy_res",
    "fire_res",
    "nature_res",
    "frost_res",
    "shadow_res",
    "arcane_res",
    "delay",
    "ammo_type",
    "RangedModRange",
    "spellid_1",
    "spelltrigger_1",
    "spellcharges_1",
    "spellppmRate_1",
    "spellcooldown_1",
    "spellcategory_1",
    "spellcategorycooldown_1",
    "spellid_2",
    "spelltrigger_2",
    "spellcharges_2",
    "spellppmRate_2",
    "spellcooldown_2",
    "spellcategory_2",
    "spellcategorycooldown_2",
    "spellid_3",
    "spelltrigger_3",
    "spellcharges_3",
    "spellppmRate_3",
    "spellcooldown_3",
    "spellcategory_3",
    "spellcategorycooldown_3",
    "spellid_4",
    "spelltrigger_4",
    "spellcharges_4",
    "spellppmRate_4",
    "spellcooldown_4",
    "spellcategory_4",
    "spellcategorycooldown_4",
    "spellid_5",
    "spelltrigger_5",
    "spellcharges_5",
    "spellppmRate_5",
    "spellcooldown_5",
    "spellcategory_5",
    "spellcategorycooldown_5",
    "bonding",
    "description",
    "PageText",
    "LanguageID",
    "PageMaterial",
    "startquest",
    "lockid",
    "Material",
    "sheath",
    "RandomProperty",
    "block",
    "itemset",
    "MaxDurability",
    "area",
    "Map",
    "BagFamily",
    "ScriptName",
    "DisenchantID",
    "FoodType",
    "minMoneyLoot",
    "maxMoneyLoot",
    "Duration",
    "ExtraFlags",
)

CREATURE_LOOT_COLUMNS: Tuple[str, ...] = (
    "entry",
    "item",
    "ChanceOrQuestChance",
    "groupid",
    "mincountOrRef",
    "maxcount",
    "condition_id",
    "comments",
)


STAT_MAP = {
    "mana": 0,
    "health": 1,
    "agility": 3,
    "strength": 4,
    "intellect": 5,
    "spirit": 6,
    "stamina": 7,
}

DAMAGE_TYPE_MAP = {
    "physical": 0,
    "holy": 1,
    "fire": 2,
    "nature": 3,
    "frost": 4,
    "shadow": 5,
    "arcane": 6,
}


@dataclass
class ItemTemplate:
    values: Dict[str, object]

    def to_sql(self) -> str:
        serialized = []
        for column in ITEM_TEMPLATE_COLUMNS:
            value = self.values.get(column)
            if isinstance(value, str):
                escaped = value.replace("'", "\\'")
                serialized.append(f"'{escaped}'")
            elif isinstance(value, float):
                serialized.append(str(float(value)))
            else:
                serialized.append(str(int(value)))
        columns = ", ".join(f"`{col}`" for col in ITEM_TEMPLATE_COLUMNS)
        values = ", ".join(serialized)
        return f"REPLACE INTO `item_template` ({columns}) VALUES ({values});"


@dataclass
class CreatureLoot:
    values: Dict[str, object]

    def to_sql(self) -> str:
        serialized = []
        for column in CREATURE_LOOT_COLUMNS:
            value = self.values.get(column)
            if isinstance(value, str):
                escaped = value.replace("'", "\\'")
                serialized.append(f"'{escaped}'")
            elif isinstance(value, float):
                serialized.append(str(float(value)))
            else:
                serialized.append(str(int(value)))
        columns = ", ".join(f"`{col}`" for col in CREATURE_LOOT_COLUMNS)
        values = ", ".join(serialized)
        return f"REPLACE INTO `creature_loot_template` ({columns}) VALUES ({values});"


def _default_item_row() -> Dict[str, object]:
    data: Dict[str, object] = {
        "entry": 0,
        "class": 0,
        "subclass": 0,
        "name": "",
        "displayid": 0,
        "Quality": 0,
        "Flags": 0,
        "BuyCount": 1,
        "BuyPrice": 0,
        "SellPrice": 0,
        "InventoryType": 0,
        "AllowableClass": -1,
        "AllowableRace": -1,
        "ItemLevel": 0,
        "RequiredLevel": 0,
        "RequiredSkill": 0,
        "RequiredSkillRank": 0,
        "requiredspell": 0,
        "requiredhonorrank": 0,
        "RequiredCityRank": 0,
        "RequiredReputationFaction": 0,
        "RequiredReputationRank": 0,
        "maxcount": 0,
        "stackable": 1,
        "ContainerSlots": 0,
        "armor": 0,
        "holy_res": 0,
        "fire_res": 0,
        "nature_res": 0,
        "frost_res": 0,
        "shadow_res": 0,
        "arcane_res": 0,
        "delay": 1000,
        "ammo_type": 0,
        "RangedModRange": 0.0,
        "bonding": 0,
        "description": "",
        "PageText": 0,
        "LanguageID": 0,
        "PageMaterial": 0,
        "startquest": 0,
        "lockid": 0,
        "Material": 0,
        "sheath": 0,
        "RandomProperty": 0,
        "block": 0,
        "itemset": 0,
        "MaxDurability": 0,
        "area": 0,
        "Map": 0,
        "BagFamily": 0,
        "ScriptName": "",
        "DisenchantID": 0,
        "FoodType": 0,
        "minMoneyLoot": 0,
        "maxMoneyLoot": 0,
        "Duration": 0,
        "ExtraFlags": 0,
    }
    for idx in range(1, 11):
        data[f"stat_type{idx}"] = 0
        data[f"stat_value{idx}"] = 0
    for idx in range(1, 6):
        data[f"dmg_min{idx}"] = 0.0
        data[f"dmg_max{idx}"] = 0.0
        data[f"dmg_type{idx}"] = 0
        data[f"spellid_{idx}"] = 0
        data[f"spelltrigger_{idx}"] = 0
        data[f"spellcharges_{idx}"] = 0
        data[f"spellppmRate_{idx}"] = 0.0
        data[f"spellcooldown_{idx}"] = -1
        data[f"spellcategory_{idx}"] = 0
        data[f"spellcategorycooldown_{idx}"] = -1
    return data


def _default_loot_row() -> Dict[str, object]:
    return {
        "entry": 0,
        "item": 0,
        "ChanceOrQuestChance": 100.0,
        "groupid": 0,
        "mincountOrRef": 1,
        "maxcount": 1,
        "condition_id": 0,
        "comments": "",
    }


def load_store() -> Dict[str, object]:
    if STORE_PATH.exists():
        with STORE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {"items": {}, "assignments": []}


def save_store(store: Dict[str, object]) -> None:
    with STORE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2, sort_keys=True)


def parse_mysql_option_file(path: Path) -> Dict[str, str]:
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # keep original case for compatibility
    content = path.read_text(encoding="utf-8")
    first_line = next((line for line in content.splitlines() if line.strip()), "")
    if not first_line.startswith("["):
        content = "[client]\n" + content
    parser.read_string(content)
    if not parser.has_section("client"):
        raise SystemExit(f"MySQL option file {path} does not contain a [client] section")
    return {key.lower(): value for key, value in parser.items("client")}


def resolve_db_config(args: argparse.Namespace) -> Optional[DatabaseConfig]:
    if not getattr(args, "apply", False):
        return None

    option_file_values: Dict[str, str] = {}
    if getattr(args, "db_config", None):
        option_path = Path(args.db_config)
        if not option_path.exists():
            raise SystemExit(f"MySQL option file not found: {option_path}")
        option_file_values = parse_mysql_option_file(option_path)

    def _get_option(name: str, cli_value: Optional[str], default: Optional[str] = None) -> Optional[str]:
        if cli_value:
            return cli_value
        return option_file_values.get(name, default)

    host = _get_option("host", getattr(args, "db_host", None), "localhost")
    port_raw = _get_option("port", getattr(args, "db_port", None), "3306")
    user = _get_option("user", getattr(args, "db_user", None), None)
    password = _get_option("password", getattr(args, "db_password", None), "")
    database = _get_option("database", getattr(args, "db_name", None), None)
    if user is None:
        raise SystemExit("Database user is required when using --apply. Provide --db-user or configure it in the option file.")
    if database is None:
        raise SystemExit(
            "Database name is required when using --apply. Provide --db-name or configure it in the option file."
        )
    try:
        port = int(port_raw) if port_raw else 3306
    except ValueError as exc:
        raise SystemExit(f"Invalid MySQL port '{port_raw}'") from exc

    return DatabaseConfig(host=host, port=port, user=user, password=password or "", database=database)


def _auto_type(column: str, value: str) -> object:
    if column in {"name", "description", "ScriptName", "comments"}:
        return value
    if column.startswith("spellppmRate") or column.startswith("dmg_min") or column.startswith("dmg_max") or column == "RangedModRange":
        return float(value)
    if column == "ChanceOrQuestChance":
        return float(value)
    return int(value)


def add_stats(values: Dict[str, object], stats: Iterable[str]) -> None:
    for stat in stats:
        if "=" not in stat:
            raise ValueError(f"Invalid stat format '{stat}'. Expected e.g. strength=10")
        key, raw_val = stat.split("=", 1)
        key = key.strip().lower()
        if key not in STAT_MAP:
            raise ValueError(f"Unknown stat '{key}'. Allowed: {', '.join(sorted(STAT_MAP))}")
        value = int(raw_val.strip())
        type_id = STAT_MAP[key]
        for idx in range(1, 11):
            if values[f"stat_type{idx}"] in (0, type_id) and (
                values[f"stat_type{idx}"] == type_id or values[f"stat_value{idx}"] == 0
            ):
                values[f"stat_type{idx}"] = type_id
                values[f"stat_value{idx}"] = value
                break
        else:
            raise ValueError("All stat slots are already filled, remove one with --set stat_typeX=0 first")


def add_damage(values: Dict[str, object], damages: Iterable[str]) -> None:
    for dmg in damages:
        parts = dmg.split(":")
        if len(parts) != 4:
            raise ValueError("Damage format must be slot:min:max:type (type can be numeric or e.g. physical)")
        slot = int(parts[0])
        if slot < 1 or slot > 5:
            raise ValueError("Damage slot must be between 1 and 5")
        min_value = float(parts[1])
        max_value = float(parts[2])
        dtype_raw = parts[3].lower()
        dtype = DAMAGE_TYPE_MAP.get(dtype_raw, None)
        if dtype is None:
            dtype = int(parts[3]) if parts[3].isdigit() else None
        if dtype is None:
            raise ValueError(f"Unknown damage type '{parts[3]}'")
        values[f"dmg_min{slot}"] = min_value
        values[f"dmg_max{slot}"] = max_value
        values[f"dmg_type{slot}"] = dtype


def add_spells(values: Dict[str, object], spells: Iterable[str]) -> None:
    for raw in spells:
        parts = raw.split(":")
        if len(parts) != 7:
            raise ValueError(
                "Spell format must be slot:id:trigger:charges:ppm:cooldown:categorycooldown"
            )
        slot = int(parts[0])
        if slot < 1 or slot > 5:
            raise ValueError("Spell slot must be between 1 and 5")
        values[f"spellid_{slot}"] = int(parts[1])
        values[f"spelltrigger_{slot}"] = int(parts[2])
        values[f"spellcharges_{slot}"] = int(parts[3])
        values[f"spellppmRate_{slot}"] = float(parts[4])
        values[f"spellcooldown_{slot}"] = int(parts[5])
        values[f"spellcategory_{slot}"] = 0
        values[f"spellcategorycooldown_{slot}"] = int(parts[6])


def handle_item_create(args: argparse.Namespace) -> None:
    store = load_store()
    items = store.setdefault("items", {})
    entry_key = str(args.entry)
    if entry_key in items and not args.force:
        raise SystemExit(f"Item {args.entry} already exists. Use --force to overwrite.")

    values = _default_item_row()
    values.update(
        {
            "entry": int(args.entry),
            "class": int(args.class_),
            "subclass": int(args.subclass),
            "name": args.name,
            "displayid": int(args.display_id),
            "Quality": int(args.quality),
            "InventoryType": int(args.inventory_type),
            "ItemLevel": int(args.item_level),
            "RequiredLevel": int(args.required_level),
            "description": args.description or "",
        }
    )

    for pair in args.set or []:
        if "=" not in pair:
            raise SystemExit(f"Invalid --set '{pair}', expected Column=Value")
        column, value = pair.split("=", 1)
        column = column.strip()
        if column not in ITEM_TEMPLATE_COLUMNS:
            raise SystemExit(f"Unknown column '{column}'")
        values[column] = _auto_type(column, value.strip())

    if args.stats:
        add_stats(values, args.stats)
    if args.damage:
        add_damage(values, args.damage)
    if args.spell:
        add_spells(values, args.spell)

    items[entry_key] = values
    save_store(store)
    print(f"Stored item {args.entry} - {args.name}")


def handle_item_list(_: argparse.Namespace) -> None:
    store = load_store()
    items = store.get("items", {})
    if not items:
        print("No custom items stored yet.")
        return
    for entry_str, values in sorted(items.items(), key=lambda kv: int(kv[0])):
        print(f"{entry_str}: {values['name']} (class={values['class']} subclass={values['subclass']})")


def handle_item_delete(args: argparse.Namespace) -> None:
    store = load_store()
    items = store.get("items", {})
    if str(args.entry) in items:
        del items[str(args.entry)]
        save_store(store)
        print(f"Removed item {args.entry}")
    else:
        print(f"Item {args.entry} not found", file=sys.stderr)
        raise SystemExit(1)


def handle_boss_assign(args: argparse.Namespace) -> None:
    store = load_store()
    items = store.setdefault("items", {})
    if str(args.item) not in items:
        raise SystemExit(f"Item {args.item} is not defined yet. Create it first.")

    assignment = _default_loot_row()
    assignment.update(
        {
            "entry": int(args.boss),
            "item": int(args.item),
            "ChanceOrQuestChance": float(args.chance),
            "groupid": int(args.group),
            "mincountOrRef": int(args.min),
            "maxcount": int(args.max),
            "condition_id": int(args.condition),
            "comments": args.comment or "",
        }
    )

    assignments: List[Dict[str, object]] = store.setdefault("assignments", [])
    for existing in assignments:
        if existing["entry"] == assignment["entry"] and existing["item"] == assignment["item"]:
            existing.update(assignment)
            break
    else:
        assignments.append(assignment)

    save_store(store)
    print(
        f"Assigned item {args.item} to boss {args.boss} with {args.chance}% chance (group {args.group})"
    )


def handle_boss_list(_: argparse.Namespace) -> None:
    store = load_store()
    assignments = store.get("assignments", [])
    if not assignments:
        print("No boss assignments stored yet.")
        return
    for row in sorted(assignments, key=lambda r: (r["entry"], r["item"])):
        print(
            f"boss={row['entry']} -> item={row['item']} chance={row['ChanceOrQuestChance']}% "
            f"min={row['mincountOrRef']} max={row['maxcount']} group={row['groupid']}"
        )


def handle_boss_remove(args: argparse.Namespace) -> None:
    store = load_store()
    assignments = store.get("assignments", [])
    new_assignments = [row for row in assignments if not (
        row["entry"] == int(args.boss) and row["item"] == int(args.item)
    )]
    if len(new_assignments) == len(assignments):
        print("Assignment not found", file=sys.stderr)
        raise SystemExit(1)
    store["assignments"] = new_assignments
    save_store(store)
    print(f"Removed loot entry boss={args.boss} item={args.item}")


def generate_item_sql(entries: Iterable[int]) -> List[str]:
    store = load_store()
    items = store.get("items", {})
    sql_lines: List[str] = []
    if not entries:
        selected = items.values()
    else:
        selected = []
        for entry in entries:
            entry_key = str(entry)
            if entry_key not in items:
                raise SystemExit(f"Item {entry} not found in store")
            selected.append(items[entry_key])
    for values in selected:
        sql_lines.append(ItemTemplate(values).to_sql())
    return sql_lines


def generate_loot_sql(bosses: Iterable[int]) -> List[str]:
    store = load_store()
    assignments = store.get("assignments", [])
    if not assignments:
        return []
    if not bosses:
        selected = assignments
    else:
        boss_set = {int(b) for b in bosses}
        selected = [row for row in assignments if int(row["entry"]) in boss_set]
    return [CreatureLoot(row).to_sql() for row in selected]


def apply_sql_statements(statements: List[str], db_config: DatabaseConfig) -> None:
    if not statements:
        print("No SQL statements to apply.")
        return

    import mysql.connector

    try:
        connection = mysql.connector.connect(
            host=db_config.host,
            port=db_config.port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.database,
        )
    except mysql.connector.Error as exc:  # type: ignore[attr-defined]
        raise SystemExit(f"Failed to connect to MySQL: {exc}") from exc

    try:
        cursor = connection.cursor()
        try:
            for statement in statements:
                cursor.execute(statement)
        except mysql.connector.Error as exc:  # type: ignore[attr-defined]
            connection.rollback()
            raise SystemExit(f"Failed to execute SQL statement: {exc}") from exc
        else:
            connection.commit()
            print(f"Applied {len(statements)} SQL statements to {db_config.database}")
        finally:
            cursor.close()
    finally:
        connection.close()


def handle_sql(args: argparse.Namespace) -> None:
    item_entries = [int(entry) for entry in args.items or []]
    boss_entries = [int(entry) for entry in args.bosses or []]
    statements: List[str] = []
    statements.extend(generate_item_sql(item_entries))
    statements.extend(generate_loot_sql(boss_entries))

    output = "\n".join(statements)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {len(statements)} statements to {args.output}")
    else:
        print(output)

    db_config = resolve_db_config(args)
    if db_config:
        apply_sql_statements(statements, db_config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-config", help="Path to a MySQL option file (e.g. connection.cnf)")
    parser.add_argument("--db-host", dest="db_host", help="MySQL host")
    parser.add_argument("--db-port", dest="db_port", help="MySQL port")
    parser.add_argument("--db-user", dest="db_user", help="MySQL user")
    parser.add_argument("--db-password", dest="db_password", help="MySQL password")
    parser.add_argument("--db-name", dest="db_name", help="MySQL database name")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("item", help="Manage custom items")
    item_sub = create.add_subparsers(dest="item_command", required=True)

    item_create = item_sub.add_parser("create", help="Create or overwrite an item")
    item_create.add_argument("--entry", type=int, required=True)
    item_create.add_argument("--name", required=True)
    item_create.add_argument("--class", dest="class_", type=int, required=True)
    item_create.add_argument("--subclass", type=int, required=True)
    item_create.add_argument("--quality", type=int, required=True)
    item_create.add_argument("--display-id", dest="display_id", type=int, required=True)
    item_create.add_argument("--inventory-type", type=int, required=True)
    item_create.add_argument("--item-level", dest="item_level", type=int, default=0)
    item_create.add_argument("--required-level", dest="required_level", type=int, default=0)
    item_create.add_argument("--description", default="")
    item_create.add_argument("--stats", nargs="*", help="e.g. strength=20 stamina=15")
    item_create.add_argument(
        "--damage",
        nargs="*",
        help="slot:min:max:type (type can be numeric or physical/holy/fire/nature/frost/shadow/arcane)",
    )
    item_create.add_argument(
        "--spell",
        nargs="*",
        help="slot:id:trigger:charges:ppm:cooldown:categorycooldown",
    )
    item_create.add_argument("--set", nargs="*", help="Extra Column=Value overrides")
    item_create.add_argument("--force", action="store_true", help="Overwrite existing item")
    item_create.set_defaults(func=handle_item_create)

    item_list = item_sub.add_parser("list", help="List stored items")
    item_list.set_defaults(func=handle_item_list)

    item_delete = item_sub.add_parser("delete", help="Remove an item from the store")
    item_delete.add_argument("entry", type=int)
    item_delete.set_defaults(func=handle_item_delete)

    boss = sub.add_parser("boss", help="Manage boss loot assignments")
    boss_sub = boss.add_subparsers(dest="boss_command", required=True)

    boss_assign = boss_sub.add_parser("assign", help="Assign an item to a boss")
    boss_assign.add_argument("--boss", type=int, required=True, help="Creature entry id")
    boss_assign.add_argument("--item", type=int, required=True, help="Item entry id")
    boss_assign.add_argument("--chance", type=float, required=True, help="Drop chance in percent")
    boss_assign.add_argument("--group", type=int, default=0)
    boss_assign.add_argument("--min", type=int, default=1)
    boss_assign.add_argument("--max", type=int, default=1)
    boss_assign.add_argument("--condition", type=int, default=0)
    boss_assign.add_argument("--comment", default="")
    boss_assign.set_defaults(func=handle_boss_assign)

    boss_list = boss_sub.add_parser("list", help="List stored boss assignments")
    boss_list.set_defaults(func=handle_boss_list)

    boss_remove = boss_sub.add_parser("remove", help="Delete a boss->item assignment")
    boss_remove.add_argument("--boss", type=int, required=True)
    boss_remove.add_argument("--item", type=int, required=True)
    boss_remove.set_defaults(func=handle_boss_remove)

    sql = sub.add_parser("sql", help="Generate SQL statements")
    sql.add_argument("--items", nargs="*", help="Specific item entries to export")
    sql.add_argument("--bosses", nargs="*", help="Specific boss entries to export")
    sql.add_argument("--output", help="Write SQL to file instead of stdout")
    sql.add_argument("--apply", action="store_true", help="Execute the generated SQL statements against the database")
    sql.set_defaults(func=handle_sql)

    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
