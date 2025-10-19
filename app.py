import streamlit as st
import random
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Smart Lineup Rotator", page_icon="⚽", layout="wide")
st.title("⚽ Smart Football Lineup Generator - Editable Intervals & Corrected Minutes")
st.markdown("Genera rotaciones equilibradas, permite editar posiciones, recalcula minutos y asegura que todos jueguen.")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Match Settings")
quarters = st.sidebar.slider("Number of Parts", 1, 4, 4)
divisions = st.sidebar.slider("Number of Intervals per Part", 1, 4, 2)
intervals = quarters * divisions
num_players = st.sidebar.slider("Number of players", 6, 8, 7)
ignore_gk = st.sidebar.checkbox("❌ Do not count goalkeeper minutes", value=True)

# --- FORMACIÓN FIJA ---
formation_x = {
    "Goalkeeper": 0.5,
    "Defender": 3,
    "Midfielder1": 5,
    "Midfielder2": 5,
    "Forward": 7.5,
}
formation_y = {
    "Goalkeeper": 3,
    "Defender": 3,
    "Midfielder1": 4.5,
    "Midfielder2": 1.5,
    "Forward": 3,
}

# --- PLAYER INPUT ---
st.markdown("### 👥 Player list and preferred positions")
positions = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
players = {}
for i in range(num_players):
    col1, col2 = st.columns([2, 3])
    name = col1.text_input(f"Player {i+1}", key=f"name_{i}")
    fav_positions = col2.multiselect("Preferred positions", positions, default=[], key=f"pos_{i}")
    if name:
        players[name] = fav_positions

all_players = list(players.keys())

# --- Helpers: compute minutes from a list of lineups ---
def compute_minutes(lineups, all_players, ignore_gk_flag, max_gk_per_player=1):
    minutes = defaultdict(int)
    gk_count = defaultdict(int)
    for lineup in lineups:
        for pos, p in lineup.items():
            if pos == "Goalkeeper":
                gk_count[p] += 1
                if not ignore_gk_flag:
                    minutes[p] += 1
            else:
                minutes[p] += 1
    # Ensure every player has a key
    for p in all_players:
        minutes.setdefault(p, 0)
    return minutes, gk_count

# --- Helper: ensure every player appears at least once by injecting missing players ---
def ensure_all_players_present(lineups, all_players, minutes_played, gk_count, ignore_gk_flag, max_gk_per_player=1):
    """
    For any player missing entirely (minutes=0), try to insert them into a lineup by
    replacing a player with higher minutes, without breaking GK limit.
    Returns modified lineups and updated minutes and gk_count.
    """
    missing = [p for p in all_players if minutes_played.get(p, 0) == 0]
    attempts = 0
    while missing and attempts < 50:
        attempts += 1
        changed = False
        # recompute sorted players by minutes (highest first) as candidates to replace
        sorted_by_minutes = sorted(minutes_played.items(), key=lambda x: x[1], reverse=True)
        for m_player in missing[:]:
            inserted = False
            # try each interval (earliest first) to find a place where replacement is sensible
            for idx, lineup in enumerate(lineups):
                # If m_player already in this lineup, it's not missing anymore
                if m_player in lineup.values():
                    missing.remove(m_player)
                    inserted = True
                    changed = True
                    break
                # find a player in this lineup we can replace:
                for pos, current in lineup.items():
                    # do not replace with the same player obviously
                    if current == m_player:
                        continue
                    # if replacing GK, check GK limits
                    if pos == "Goalkeeper":
                        # can't make m_player GK if they already reached limit
                        # and can't remove current GK if that would make them never appear - acceptable
                        if gk_count.get(m_player, 0) >= max_gk_per_player:
                            continue
                    # check that replacing won't violate uniqueness in that lineup
                    if m_player in lineup.values():
                        continue
                    # Replace if current has more minutes than m_player (so we even out)
                    if minutes_played.get(current, 0) > minutes_played.get(m_player, 0):
                        # perform replacement
                        lineup[pos] = m_player
                        # update minutes/gk_count locally (we'll recompute fully after all replacements)
                        inserted = True
                        changed = True
                        break
                if inserted:
                    missing.remove(m_player)
                    break
        if not changed:
            break
        # recompute minutes/gk_count after changes
        minutes_played, gk_count = compute_minutes(lineups, all_players, ignore_gk_flag, max_gk_per_player)
        missing = [p for p in all_players if minutes_played.get(p, 0) == 0]
    return lineups, minutes_played, gk_count

# --- State: keep lineups in session_state so edits persist across reruns ---
if "lineups" not in st.session_state:
    st.session_state["lineups"] = None
if "edited_lineups" not in st.session_state:
    st.session_state["edited_lineups"] = None

# --- Generate rotations button ---
if st.button("🎲 Generate Rotations"):
    if len(players) < 6:
        st.error("You must enter at least 6 players.")
    else:
        st.success("✅ Generating fair rotations...")

        field_positions = list(formation_x.keys())
        max_gk_per_player = 1
        best_lineups = None
        best_diff = float("inf")

        # Search attempts to balance minutes
        for attempt in range(800):
            minutes_played = defaultdict(int)
            gk_count = defaultdict(int)
            lineups = []
            # Start with a balanced initial starters: choose sample of 5 but try to vary
            previous_starters = random.sample(all_players, 5)
            used_players = set(previous_starters)

            for _ in range(intervals):
                lineup = {}
                available = previous_starters.copy()
                assigned = []
                for pos in field_positions:
                    candidates = [p for p in available if pos in players[p]] or available.copy()
                    if pos == "Goalkeeper":
                        # prefer candidates who haven't been GK maxed
                        c2 = [p for p in candidates if gk_count[p] < max_gk_per_player]
                        if c2:
                            candidates = c2
                    # choose player with minimum minutes (to balance)
                    player = min(candidates, key=lambda x: minutes_played[x])
                    lineup[pos] = player
                    assigned.append(player)
                    available.remove(player)
                # update minutes/gk_count
                for pos, p in lineup.items():
                    if pos == "Goalkeeper":
                        gk_count[p] += 1
                        if not ignore_gk:
                            minutes_played[p] += 1
                    else:
                        minutes_played[p] += 1
                    used_players.add(p)
                lineups.append(lineup)
                # compute resting and form next previous_starters (rotate)
                resting = [p for p in all_players if p not in assigned]
                if resting:
                    # choose who rests (random among assigned) to match number of resting players
                    to_rest = random.sample(assigned, len(resting))
                    previous_starters = [p for p in assigned if p not in to_rest] + resting
                else:
                    previous_starters = assigned

            # if someone never played, penalize them to force inclusion next attempts
            if len(used_players) < len(all_players):
                for p in all_players:
                    if p not in used_players:
                        minutes_played[p] = 0

            max_m = max(minutes_played.values())
            min_m = min(minutes_played.values())
            diff = max_m - min_m

            # keep best
            if diff < best_diff:
                best_diff = diff
                best_lineups = lineups

            # early stop if good enough and everyone used
            if diff <= 1 and len(used_players) == len(all_players):
                break

        # save to session_state
        st.session_state["lineups"] = best_lineups
        st.session_state["edited_lineups"] = [ln.copy() for ln in best_lineups]
        st.experimental_rerun()  # rerun to show generated lineups immediately

# If we have lineups in session_state, use them
lineups = st.session_state.get("edited_lineups")
if lineups is None:
    st.info("Genera las rotaciones para poder editarlas.")
else:
    field_positions = list(formation_x.keys())

    # --- Show and allow editing ---
    st.markdown("## 🔍 Generated Intervals (edit if needed)")
    for i, lineup in enumerate(lineups, 1):
        st.subheader(f"Interval {i}")
        resting_players = [p for p in all_players if p not in lineup.values()]
        st.write("Resting players:", ", ".join(resting_players) if resting_players else "None")

        # Draw field
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.add_patch(patches.Rectangle((0, 0), 10, 6, linewidth=2, edgecolor='green', facecolor='lightgreen'))
        ax.add_patch(patches.Circle((5, 3), 1, linewidth=2, edgecolor='white', facecolor='none'))
        ax.plot([5, 5], [0, 6], color='white', linewidth=2)
        ax.plot([0, 10], [3, 3], color='white', linewidth=1)
        ax.add_patch(patches.Rectangle((0, 2), 1.5, 2, linewidth=2, edgecolor='white', facecolor='none'))
        ax.add_patch(patches.Rectangle((8.5, 2), 1.5, 2, linewidth=2, edgecolor='white', facecolor='none'))
        ax.set_xlim(0, 10)
        ax.set_ylim(-1, 6)
        ax.axis('off')

        for pos, player_name in lineup.items():
            ax.text(formation_x[pos], formation_y[pos], player_name, ha='center', va='center', fontsize=10,
                    bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))

        for idx, sub in enumerate(resting_players):
            ax.text(1 + idx * 2, -0.5, sub, ha='center', va='center', fontsize=9,
                    bbox=dict(facecolor='gray', alpha=0.7, boxstyle='round'))

        st.pyplot(fig)

    # --- EDIT SECTION ---
    st.markdown("## ✏️ Edit Intervals")
    edited = False
    for i in range(1, len(lineups) + 1):
        with st.expander(f"Edit Interval {i}", expanded=False):
            current = st.session_state["edited_lineups"][i - 1]
            # build selectboxes with validation to avoid duplicates
            selections = {}
            used_in_this_interval = set()
            duplicate_flag = False
            for pos in field_positions:
                default_index = max(0, list(all_players).index(current[pos]) if current[pos] in all_players else 0)
                sel = st.selectbox(f"{pos} (Interval {i})", options=all_players, index=default_index, key=f"edit_{i}_{pos}")
                selections[pos] = sel
                if sel in used_in_this_interval:
                    duplicate_flag = True
                used_in_this_interval.add(sel)
            if duplicate_flag:
                st.error("Cada posición debe tener un jugador distinto en este intervalo. Corrige duplicados antes de guardar.")
            else:
                if st.button(f"💾 Save changes for Interval {i}", key=f"save_{i}"):
                    # apply changes
                    st.session_state["edited_lineups"][i - 1] = selections.copy()
                    st.success(f"✅ Interval {i} updated.")
                    edited = True

    # If any edit was made, we should recalc minutes and ensure inclusion
    if edited:
        lineups = st.session_state["edited_lineups"]

    # --- Recalculate minutes from edited_lineups and ensure inclusion ---
    minutes_played, gk_count = compute_minutes(lineups, all_players, ignore_gk, max_gk_per_player=1)
    # enforce that every player appears at least once by inserting if necessary
    lineups, minutes_played, gk_count = ensure_all_players_present(lineups, all_players, minutes_played, gk_count, ignore_gk, max_gk_per_player=1)
    # recompute after possible adjustments
    minutes_played, gk_count = compute_minutes(lineups, all_players, ignore_gk, max_gk_per_player=1)

    # save back edited lineups (in case ensure_all_players_present modified them)
    st.session_state["edited_lineups"] = [ln.copy() for ln in lineups]

    # --- SUMMARY ---
    st.markdown(f"### ⏱️ Summary of minutes played (Goalkeeper not counted: {'Yes' if ignore_gk else 'No'})")
    # prepare summary data
    summary_data = sorted(minutes_played.items(), key=lambda x: x[1], reverse=True)
    # show table with minutes and percentage of total intervals (note: GK excluded if selected)
    st.table([(p, m, f"{(m / intervals * 100):.1f}%") for p, m in summary_data])

    # --- PDF GENERATION (uses edited_lineups) ---
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=landscape(letter))

    def draw_field_pdf(c, x_offset, y_offset, lineup, resting_players):
        c.setFillColorRGB(0.7, 1, 0.7)
        c.rect(x_offset, y_offset, 300, 180, fill=1)
        c.setStrokeColorRGB(1, 1, 1)
        c.setLineWidth(2)
        c.line(x_offset + 150, y_offset, x_offset + 150, y_offset + 180)
        c.line(x_offset, y_offset + 90, x_offset + 300, y_offset + 90)
        c.circle(x_offset + 150, y_offset + 90, 30)
        c.rect(x_offset, y_offset + 60, 45, 60, stroke=1, fill=0)
        c.rect(x_offset + 255, y_offset + 60, 45, 60, stroke=1, fill=0)

        for pos, player_name in lineup.items():
            x = x_offset + (formation_x[pos] / 10) * 300
            y = y_offset + (formation_y[pos] / 6) * 180
            # mark GK with a small "G" box color for clarity
            if pos == "Goalkeeper":
                c.setFillColorRGB(0.9, 0.9, 0.6)
                c.rect(x - 17, y - 12, 34, 24, fill=1)
            else:
                c.setFillColorRGB(1, 1, 1)
                c.rect(x - 15, y - 10, 30, 20, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x, y, player_name)

        for idx, sub in enumerate(resting_players):
            sub_x = x_offset + 40 + idx * 50
            sub_y = y_offset - 25
            c.setFillColorRGB(0.6, 0.6, 0.6)
            c.rect(sub_x - 15, sub_y - 10, 30, 20, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(sub_x, sub_y, sub)

    intervals_per_page = 4
    edited_lineups = st.session_state["edited_lineups"]
    for page_start in range(0, len(edited_lineups), intervals_per_page):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20, 560, f"Smart Lineup Rotations - {datetime.now().strftime('%Y-%m-%d')}")
        c.setFont("Helvetica", 10)
        c.drawString(20, 545, f"Players: {', '.join(all_players)}")
        c.drawString(20, 530, f"Goalkeeper time excluded: {'Yes' if ignore_gk else 'No'}")
        y_positions = [350, 100]
        for idx, i in enumerate(range(page_start, min(page_start + intervals_per_page, len(edited_lineups)), 2)):
            y_offset = y_positions[idx % 2]
            lineup1 = edited_lineups[i]
            resting1 = [p for p in all_players if p not in lineup1.values()]
            draw_field_pdf(c, 50, y_offset, lineup1, resting1)
            if i + 1 < len(edited_lineups):
                lineup2 = edited_lineups[i + 1]
                resting2 = [p for p in all_players if p not in lineup2.values()]
                draw_field_pdf(c, 400, y_offset, lineup2, resting2)
        c.showPage()

    # Final summary page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(250, 550, "Summary of Minutes Played")
    c.setFont("Helvetica", 12)
    y = 500
    for player, mins in summary_data:
        c.drawString(280, y, f"{player}: {mins} intervals")
        y -= 20
    c.showPage()
    c.save()

    pdf_buffer.seek(0)
    st.markdown("### 📄 Download Professional PDF")
    st.download_button(
        label="Download PDF",
        data=pdf_buffer,
        file_name="lineup_rotations.pdf",
        mime="application/pdf"
    )
