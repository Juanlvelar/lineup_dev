import streamlit as st
import random
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from datetime import datetime

# --- CONFIG INICIAL ---
st.set_page_config(page_title="Smart Lineup Rotator", page_icon="⚽", layout="wide")
st.title("⚽ Smart Football Lineup Generator - Fair Playtime Edition")
st.markdown("Genera rotaciones equilibradas, permite editar posiciones y descargar PDF profesional.")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Match Settings")
quarters = st.sidebar.slider("Number of Parts", 1, 4, 4)
divisions = st.sidebar.slider("Number of Intervals per Part", 1, 4, 2)
intervals = quarters * divisions  # 6 u 8 intervalos
num_players = st.sidebar.slider("Number of players", 6, 8, 7)
ignore_gk = st.sidebar.checkbox("❌ Do not count goalkeeper minutes", value=True)

# --- FORMACIÓN FIJA EN DIAMANTE ---
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

# --- ENTRADA DE JUGADORES ---
st.markdown("### 👥 Player list and preferred positions")
positions = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
players = {}
for i in range(num_players):
    col1, col2 = st.columns([2, 3])
    name = col1.text_input(f"Player {i+1}", key=f"name_{i}")
    fav_positions = col2.multiselect("Preferred positions", positions, default=[], key=f"pos_{i}")
    if name:
        players[name] = fav_positions

# --- GENERAR ROTACIONES ---
if st.button("🎲 Generate Rotations"):
    if len(players) < 6:
        st.error("You must enter at least 6 players.")
    else:
        st.success("✅ Generating fair rotations...")

        field_positions = list(formation_x.keys())
        all_players = list(players.keys())
        max_gk_per_player = 1

        best_lineups = None
        best_diff = float("inf")

        # --- INTENTOS DE EQUILIBRIO ---
        for attempt in range(500):
            minutes_played = defaultdict(int)
            gk_count = defaultdict(int)
            lineups = []
            previous_starters = random.sample(all_players, 5)
            used_players = set(previous_starters)

            for _ in range(intervals):
                lineup = {}
                available = previous_starters.copy()
                assigned = []

                for pos in field_positions:
                    candidates = [p for p in available if pos in players[p]] or available.copy()
                    if pos == "Goalkeeper":
                        candidates = [p for p in candidates if gk_count[p] < max_gk_per_player] or candidates
                    player = min(candidates, key=lambda x: minutes_played[x])
                    lineup[pos] = player
                    assigned.append(player)
                    available.remove(player)

                for pos, player in lineup.items():
                    if pos == "Goalkeeper":
                        gk_count[player] += 1
                        if not ignore_gk:
                            minutes_played[player] += 1
                    else:
                        minutes_played[player] += 1
                    used_players.add(player)

                lineups.append(lineup)

                resting = [p for p in all_players if p not in assigned]
                if resting:
                    to_rest = random.sample(assigned, len(resting))
                    previous_starters = [p for p in assigned if p not in to_rest] + resting
                else:
                    previous_starters = assigned

            # Asegura que todos juegan al menos una vez
            if len(used_players) < len(all_players):
                for p in all_players:
                    if p not in used_players:
                        minutes_played[p] = 0

            max_m = max(minutes_played.values())
            min_m = min(minutes_played.values())
            diff = max_m - min_m

            if diff < best_diff:
                best_diff = diff
                best_lineups = lineups

            if diff <= 1 and len(used_players) == len(all_players):
                break

        lineups = best_lineups
        edited_lineups = lineups.copy()

        # --- VISUALIZACIÓN ---
        for i, lineup in enumerate(lineups, 1):
            st.subheader(f"🕐 Interval {i}")
            resting_players = [p for p in all_players if p not in lineup.values()]
            st.write("Resting players:", ", ".join(resting_players) if resting_players else "None")

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

        # --- EDICIÓN DE INTERVALOS ---
        st.markdown("## ✏️ Edit Rotations (optional)")
        for i, lineup in enumerate(lineups, 1):
            with st.expander(f"Edit Interval {i}"):
                st.write("Adjust player positions below:")
                edited = {}
                for pos in field_positions:
                    edited[pos] = st.selectbox(
                        f"{pos}",
                        options=list(players.keys()),
                        index=list(players.keys()).index(lineup[pos]) if lineup[pos] in players else 0,
                        key=f"edit_{i}_{pos}"
                    )
                if st.button(f"💾 Save changes for Interval {i}", key=f"save_{i}"):
                    edited_lineups[i - 1] = edited
                    st.success(f"✅ Interval {i} updated successfully.")

        # --- RESUMEN ---
        st.markdown(f"### ⏱️ Summary of minutes played (Goalkeeper not counted: {'Yes' if ignore_gk else 'No'})")
        summary_data = sorted(minutes_played.items(), key=lambda x: x[1], reverse=True)
        st.table([(p, m, f"{(m / intervals * 100):.1f}%") for p, m in summary_data])

        # --- PDF ---
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

        # --- PÁGINA DE RESUMEN ---
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
