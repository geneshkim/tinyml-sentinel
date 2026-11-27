"""Print a scenario with event indices, for hand labelling and quality checks.

    python show.py samples/scenarios/hand_implicit_001.jsonl
    python show.py work/rootse/scenarios/<id>.jsonl --width 300 --around 12
If the folder has labels.jsonl, the from_event of each agent is marked.
"""
import argparse
import os

from schema import read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--width", type=int, default=160, help="characters of text per event")
    ap.add_argument("--around", type=int, help="only show events near this index")
    ap.add_argument("--radius", type=int, default=4)
    args = ap.parse_args()
    events = read_jsonl(args.scenario)
    sid = os.path.basename(args.scenario)[:-6]
    labels_path = os.path.join(os.path.dirname(os.path.dirname(args.scenario)), "labels.jsonl")
    marks = {}
    if os.path.exists(labels_path):
        for lab in read_jsonl(labels_path):
            if lab["scenario"] == sid:
                print(f"label: agent {lab['agent']} case={lab['case']} from_event={lab.get('from_event', '-')}")
                if "from_event" in lab:
                    marks[lab["from_event"]] = f"  <== from_event ({lab['case']})"
    for ev in events:
        if args.around is not None and abs(ev["i"] - args.around) > args.radius:
            continue
        text = " ".join(ev["text"].split())
        if len(text) > args.width:
            text = text[: args.width] + "..."
        print(f"{ev['i']:>4} {ev['agent']} {ev['type']:<6} {text}{marks.get(ev['i'], '')}")


if __name__ == "__main__":
    main()
