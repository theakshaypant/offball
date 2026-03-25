SPEED_ZONE_BINS   = [0, 7, 14, 21, 25, float('inf')]
SPEED_ZONE_LABELS = ['Walking', 'Jogging', 'Running', 'High-Speed Running', 'Sprinting']
SPEED_ZONE_COLORS = ['#4CAF50', '#FFC107', '#FF5722', '#E91E63', '#9C27B0']

HR_ZONE_LABELS      = ['Z1 Easy', 'Z2 Fat Burn', 'Z3 Aerobic', 'Z4 Threshold', 'Z5 Anaerobic']
HR_ZONE_COLORS      = ['#a8d8a8', '#ffe083', '#ffa84c', '#ff6b35', '#d62246']
HR_ZONE_MULTIPLIERS = [1, 2, 3, 4, 5]

GARMIN_NS = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'

ARCHETYPES = {
    'Goalkeeper': {
        'pace': 48, 'physical': 55, 'stamina': 85, 'explosiveness': 62, 'work_rate': 65,
        'description': 'The last line of defence. Explosive reactions, commanding presence in the box, and shot-stopping instincts — covering limited ground but with massive impact.',
        'position': 'GK', 'color': '#FFD700', 'icon': '🧤',
    },
    'Box-to-Box Midfielder': {
        'pace': 72, 'physical': 88, 'stamina': 90, 'explosiveness': 65, 'work_rate': 90,
        'description': 'The engine of the team — covers every blade of grass with relentless energy, contributing at both ends and never stopping.',
        'position': 'CM', 'color': '#4CAF50', 'icon': '⚙️',
    },
    'Pressing Machine': {
        'pace': 78, 'physical': 82, 'stamina': 88, 'explosiveness': 75, 'work_rate': 95,
        'description': 'Never stops running. High press, relentless intensity — closes down every inch of space and wears opponents down with sheer work rate.',
        'position': 'CF/LW', 'color': '#FF5722', 'icon': '🔥',
    },
    'Pacey Winger': {
        'pace': 93, 'physical': 65, 'stamina': 72, 'explosiveness': 93, 'work_rate': 68,
        'description': 'Electric on the flanks. Relies on explosive pace and burst runs to leave defenders in the dust and create chances from wide.',
        'position': 'LW/RW', 'color': '#2196F3', 'icon': '⚡',
    },
    'Inverted Winger': {
        'pace': 85, 'physical': 68, 'stamina': 75, 'explosiveness': 88, 'work_rate': 72,
        'description': 'Cuts inside from the flank to shoot or combine. Dangerous in tight spaces with quick directional changes and burst acceleration.',
        'position': 'LW/RW', 'color': '#00BCD4', 'icon': '🌀',
    },
    'Target Man': {
        'pace': 68, 'physical': 88, 'stamina': 70, 'explosiveness': 70, 'work_rate': 72,
        'description': 'Physical presence up top. Holds up play, brings teammates into the game, and is a dominant threat in the air and on the ground.',
        'position': 'ST', 'color': '#FF9800', 'icon': '🎯',
    },
    'Complete Forward': {
        'pace': 85, 'physical': 82, 'stamina': 80, 'explosiveness': 83, 'work_rate': 82,
        'description': 'The total striker — dangerous in every situation. Combines pace, physicality, and intelligent movement to threaten defences in multiple ways.',
        'position': 'ST', 'color': '#F44336', 'icon': '⭐',
    },
    'False 9': {
        'pace': 74, 'physical': 68, 'stamina': 82, 'explosiveness': 72, 'work_rate': 85,
        'description': 'Drops deep to collect, link play, and create space for runners. Consistent movement across the pitch with a high football IQ.',
        'position': 'ST/CAM', 'color': '#E91E63', 'icon': '🧠',
    },
    'Trequartista': {
        'pace': 78, 'physical': 62, 'stamina': 72, 'explosiveness': 80, 'work_rate': 70,
        'description': 'The creative spark between the lines. Floats into pockets of space, operates in bursts, and unlocks defences with moments of brilliance.',
        'position': 'CAM', 'color': '#AB47BC', 'icon': '✨',
    },
    'Deep-lying Playmaker': {
        'pace': 62, 'physical': 72, 'stamina': 78, 'explosiveness': 50, 'work_rate': 78,
        'description': 'The metronome. Controls tempo with intelligent positioning and measured, precise movement — always available, never flashy.',
        'position': 'CDM/CM', 'color': '#9C27B0', 'icon': '🎮',
    },
    'Holding Midfielder': {
        'pace': 58, 'physical': 82, 'stamina': 80, 'explosiveness': 52, 'work_rate': 75,
        'description': 'The defensive anchor. Sits in front of the backline, wins duels, and recycles possession — physical, positional, and dependable.',
        'position': 'CDM', 'color': '#78909C', 'icon': '⚓',
    },
    'Wing Back': {
        'pace': 82, 'physical': 75, 'stamina': 90, 'explosiveness': 76, 'work_rate': 88,
        'description': 'Bombs up and down the flank relentlessly. High stamina is the defining trait — effective both defensively and as an attacking outlet.',
        'position': 'LWB/RWB', 'color': '#26C6DA', 'icon': '🏃',
    },
    'Ball-playing Defender': {
        'pace': 72, 'physical': 85, 'stamina': 80, 'explosiveness': 66, 'work_rate': 75,
        'description': 'Reads the game with composure and authority. Steady under pressure with the occasional surge forward to join attacks.',
        'position': 'CB', 'color': '#607D8B', 'icon': '🛡️',
    },
    'Sweeper': {
        'pace': 78, 'physical': 80, 'stamina': 78, 'explosiveness': 70, 'work_rate': 72,
        'description': 'The last defender with the freedom to roam. Covers space behind the backline and uses pace to recover when needed.',
        'position': 'CB/SW', 'color': '#546E7A', 'icon': '🧹',
    },
    'Physical Powerhouse': {
        'pace': 70, 'physical': 95, 'stamina': 75, 'explosiveness': 72, 'work_rate': 80,
        'description': 'Built like a freight train. Wins every physical contest — dominant in the air, powerful in duels, and a presence no opponent enjoys facing.',
        'position': 'ST/CB', 'color': '#8D6E63', 'icon': '💪',
    },
}
