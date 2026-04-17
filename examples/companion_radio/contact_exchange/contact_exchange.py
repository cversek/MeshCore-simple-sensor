#!/usr/bin/env python3
"""
Exchange contacts between two MeshCore companion nodes via USB serial.

This script connects to companion radio nodes and exchanges their contact
(business card) information so they can send direct messages to each other.

Usage:
  # Exchange contacts between two nodes (both connected via USB):
  python contact_exchange.py exchange /dev/ttyUSB0 /dev/ttyACM0

  # Export a node's own contact card:
  python contact_exchange.py export /dev/ttyUSB0
  python contact_exchange.py export /dev/ttyUSB0 --output card.txt

  # Import a contact card into a node:
  python contact_exchange.py import /dev/ttyACM0 --card "meshcore://ab01cd..."
  python contact_exchange.py import /dev/ttyACM0 --input card.txt

Requirements:
  pip install meshcore
"""

import asyncio
import argparse
import sys

from meshcore import MeshCore, EventType


async def connect_node(port, baud=115200):
    """Connect to a companion node via serial. Returns MeshCore instance."""
    node = await MeshCore.create_serial(port, baud)
    if node is None:
        print(f"Error: Could not connect to node on {port}", file=sys.stderr)
        sys.exit(1)
    return node


def get_node_name(node):
    """Get the node's display name from self_info."""
    info = node.self_info
    if info and "name" in info:
        return info["name"]
    return "unknown"


def get_node_pubkey(node):
    """Get the node's public key hex prefix from self_info."""
    info = node.self_info
    if info and "public_key" in info:
        return info["public_key"][:12]  # first 6 bytes as hex
    return "??????"


async def export_self_card(node):
    """Export a node's own contact card as a meshcore:// URI string."""
    result = await node.commands.export_contact()
    if result.type == EventType.ERROR:
        return None
    return result.payload["uri"]


async def import_card(node, uri):
    """Import a contact card URI into a node. Returns True on success."""
    # Convert meshcore:// URI to raw bytes for the import command
    hex_str = uri
    if hex_str.startswith("meshcore://"):
        hex_str = hex_str[len("meshcore://"):]
    card_bytes = bytes.fromhex(hex_str)

    result = await node.commands.import_contact(card_bytes)
    return result.type != EventType.ERROR


async def list_contacts(node):
    """Retrieve and display the node's contact list."""
    result = await node.commands.get_contacts()
    if result.type == EventType.ERROR:
        print("  (could not retrieve contacts)")
        return

    contacts = node.contacts
    if not contacts:
        print("  (no contacts)")
        return

    for key, contact in contacts.items():
        name = contact.get("adv_name", "???")
        key_prefix = key[:12] if len(key) > 12 else key
        print(f"  - {name} [{key_prefix}...]")


async def cmd_exchange(args):
    """Exchange contacts between two nodes."""
    print(f"Connecting to Node A on {args.port_a}...")
    node_a = await connect_node(args.port_a, args.baud)
    name_a = get_node_name(node_a)
    pubkey_a = get_node_pubkey(node_a)
    print(f"  Node A: {name_a} [{pubkey_a}...]")

    print(f"Connecting to Node B on {args.port_b}...")
    node_b = await connect_node(args.port_b, args.baud)
    name_b = get_node_name(node_b)
    pubkey_b = get_node_pubkey(node_b)
    print(f"  Node B: {name_b} [{pubkey_b}...]")

    # Export self card from each node
    print(f"\nExporting {name_a}'s contact card...")
    card_a = await export_self_card(node_a)
    if card_a is None:
        print("Error: Failed to export Node A's contact card", file=sys.stderr)
        await node_a.disconnect()
        await node_b.disconnect()
        sys.exit(1)
    print(f"  OK ({len(card_a)} chars)")

    print(f"Exporting {name_b}'s contact card...")
    card_b = await export_self_card(node_b)
    if card_b is None:
        print("Error: Failed to export Node B's contact card", file=sys.stderr)
        await node_a.disconnect()
        await node_b.disconnect()
        sys.exit(1)
    print(f"  OK ({len(card_b)} chars)")

    # Import each card into the other node
    print(f"\nImporting {name_a}'s card into {name_b}...")
    if await import_card(node_b, card_a):
        print("  OK")
    else:
        print("  FAILED", file=sys.stderr)

    print(f"Importing {name_b}'s card into {name_a}...")
    if await import_card(node_a, card_b):
        print("  OK")
    else:
        print("  FAILED", file=sys.stderr)

    # Verify by listing contacts
    print(f"\n{name_a}'s contacts:")
    await list_contacts(node_a)

    print(f"\n{name_b}'s contacts:")
    await list_contacts(node_b)

    print("\nDone! Both nodes now have each other's contact information.")

    await node_a.disconnect()
    await node_b.disconnect()


async def cmd_export(args):
    """Export a node's own contact card."""
    node = await connect_node(args.port, args.baud)
    name = get_node_name(node)

    card = await export_self_card(node)
    if card is None:
        print("Error: Failed to export contact card", file=sys.stderr)
        await node.disconnect()
        sys.exit(1)

    if args.output:
        with open(args.output, "w") as f:
            f.write(card + "\n")
        print(f"Exported {name}'s card to {args.output}")
    else:
        print(f"# {name}'s contact card:")
        print(card)

    await node.disconnect()


async def cmd_import(args):
    """Import a contact card into a node."""
    # Get the card URI from argument or file
    if args.card:
        card = args.card.strip()
    elif args.input:
        with open(args.input, "r") as f:
            card = f.read().strip()
            # Skip comment lines
            lines = [l for l in card.split("\n") if not l.startswith("#")]
            card = lines[0].strip() if lines else ""
    else:
        print("Error: Provide --card or --input", file=sys.stderr)
        sys.exit(1)

    if not card.startswith("meshcore://"):
        print("Error: Card must start with 'meshcore://'", file=sys.stderr)
        sys.exit(1)

    node = await connect_node(args.port, args.baud)
    name = get_node_name(node)

    print(f"Importing card into {name}...")
    if await import_card(node, card):
        print("  OK")
        print(f"\n{name}'s contacts:")
        await list_contacts(node)
    else:
        print("  FAILED", file=sys.stderr)

    await node.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="Exchange contacts between MeshCore companion nodes"
    )
    parser.add_argument(
        "--baud", type=int, default=115200, help="Serial baud rate (default: 115200)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # exchange subcommand
    p_exchange = subparsers.add_parser(
        "exchange", help="Exchange contacts between two nodes"
    )
    p_exchange.add_argument("port_a", help="Serial port for Node A (e.g. /dev/ttyUSB0)")
    p_exchange.add_argument("port_b", help="Serial port for Node B (e.g. /dev/ttyACM0)")

    # export subcommand
    p_export = subparsers.add_parser("export", help="Export a node's contact card")
    p_export.add_argument("port", help="Serial port (e.g. /dev/ttyUSB0)")
    p_export.add_argument("--output", "-o", help="Save card to file")

    # import subcommand
    p_import = subparsers.add_parser("import", help="Import a contact card into a node")
    p_import.add_argument("port", help="Serial port (e.g. /dev/ttyUSB0)")
    p_import.add_argument("--card", "-c", help="meshcore:// URI string")
    p_import.add_argument("--input", "-i", help="Read card from file")

    args = parser.parse_args()

    if args.command == "exchange":
        asyncio.run(cmd_exchange(args))
    elif args.command == "export":
        asyncio.run(cmd_export(args))
    elif args.command == "import":
        asyncio.run(cmd_import(args))


if __name__ == "__main__":
    main()
