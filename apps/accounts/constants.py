BLOOD_GROUP_CHOICES = [
    ('A', 'A'),
    ('B', 'B'),
    ('AB', 'AB'),
    ('O', 'O'),
]

RHESUS_CHOICES = [
    ('+', 'Positive'),
    ('-', 'Negative'),
]

#: The eight (group, rhesus) pairs, in the order they are displayed in grids.
BLOOD_TYPES = [
    ('A', '+'), ('A', '-'),
    ('B', '+'), ('B', '-'),
    ('AB', '+'), ('AB', '-'),
    ('O', '+'), ('O', '-'),
]

COMPATIBILITY = {
    ('A', '+'): [('A', '+'), ('A', '-'), ('O', '+'), ('O', '-')],
    ('A', '-'): [('A', '-'), ('O', '-')],
    ('B', '+'): [('B', '+'), ('B', '-'), ('O', '+'), ('O', '-')],
    ('B', '-'): [('B', '-'), ('O', '-')],
    ('AB', '+'): [('A', '+'), ('A', '-'), ('B', '+'), ('B', '-'),
                  ('AB', '+'), ('AB', '-'), ('O', '+'), ('O', '-')],
    ('AB', '-'): [('A', '-'), ('B', '-'), ('AB', '-'), ('O', '-')],
    ('O', '+'): [('O', '+'), ('O', '-')],
    ('O', '-'): [('O', '-')],
}


def compatible_donors_for(blood_group, rhesus_factor):
    """Donor blood types that can give to this recipient type."""
    return COMPATIBILITY.get((blood_group, rhesus_factor), [])


def compatible_recipients_for(blood_group, rhesus_factor):
    """Recipient blood types a donor of this type can give to."""
    donor_type = (blood_group, rhesus_factor)
    return [recipient for recipient, donors in COMPATIBILITY.items() if donor_type in donors]
