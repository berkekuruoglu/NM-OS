# User Experience Guide

## Who Uses NM-OS

NM-OS is designed first for privacy-conscious people who do not want to become Linux or security experts.

The system does not categorize people. A student, a journalist, a retiree, and a system
administrator all use the same platform. What changes is the depth they go to and the
mode they are in at a given moment.

## Core UX Concept: Fluid Modes

The central idea is that one person has many computing moments throughout a day or week,
and the operating system should move with them  -  not force them into one posture.

**Examples of mode-switching in practice:**

| Moment | Mode | How |
|---|---|---|
| Regular morning work | Balanced (default) | No action needed  -  this is the starting state |
| Public Wi-Fi at a cafe | Hardened with Tor routing | Control Center -> Security -> Hardened |
| Exam prep  -  no distractions | Focus mode | Notifications off, distraction sites off |
| Reviewing sensitive documents | Maximum | Control Center -> Security -> Maximum -> one click |
| Done with sensitive work | Back to Balanced | Control Center -> Security -> Balanced -> one click |
| Child using the computer | Separate user account with parental limits | User settings |

Switching between modes is fast, visible, and reversible. Nothing is permanent unless the
user explicitly saves it as the new default.

## First 30 Days: User Journey

### Day 0  -  Setup

The setup assistant (greeter) runs before the first login. It has four short steps:

1. Choose your language
2. Choose your starting protection level (Balanced recommended  -  can skip)
3. Choose a browser (Firefox / Chromium / skip)
4. Choose your visual style

Total time: under two minutes. Nothing else is required.

### Day 1-3  -  Everyday Use

Users find the apps they need:

- **Files**  -  Nautilus file manager
- **Web**  -  Firefox or Chromium (whichever was chosen)
- **Email**  -  Thunderbird or Geary
- **Documents**  -  LibreOffice Writer
- **Photos**  -  Shotwell
- **Music**  -  Rhythmbox
- **Video**  -  GNOME Videos (Totem)
- **Calendar**  -  GNOME Calendar
- **Calculator**  -  GNOME Calculator

More apps are available through the **Software** app (GNOME Software + Flatpak).

### Day 7  -  Personalization

Users open the Control Center and begin adjusting:

- Wallpaper, color theme, fonts, icon set
- Dark mode vs light mode
- Dock position and size
- Accent color
- Animation speed (or turning animations off for accessibility)

### Day 14  -  Discovering Security Controls

Users who are curious open **Control Center -> Security & Privacy**.
They see their current protection level and individual toggles for each setting.
They can try turning on Tor-first networking or see what Maximum mode looks like.

### Day 30  -  Confident Daily Use

Users have set their preferred visual style, found their apps, and explored at least
one mode switch. The system feels personal and stable.

## Usage Scenarios

### Home and Family

- Write emails, browse the web, stream music and video
- Keep a photo library
- Store important documents safely (encrypted vault)
- Create a separate account for a child with appropriate limits

### Student

- Write papers in LibreOffice Writer
- Research online
- Switch to a focus mode during study sessions
- Store coursework in the encrypted vault on shared computers

### Small Business

- Manage documents and spreadsheets with LibreOffice
- Send and receive email with Thunderbird
- Store client files in the encrypted vault
- Use maximum security mode for financial tasks

### Journalist or Researcher

- Use Tor-first networking when researching sensitive topics online
- Switch to Maximum mode when handling source documents
- Encrypt notes and contacts in the vault
- Return to Balanced for everyday tasks

### Technical User

- Access all security controls individually
- Adjust per-setting overrides beyond profile defaults
- Explore network policy, sandbox, device trust, and logging options
- Use the vault, Tor, and offline mode for full isolation when needed

## Design Goals for Every Interaction

1. **No dead ends**  -  whenever the user cannot do something, explain why and offer a path forward
2. **No silent changes**  -  every setting change is visible, summarized, and reversible
3. **No jargon without explanation**  -  "Tor-first" links to a one-line plain-language description
4. **No forced steps**  -  every setup step can be skipped and revisited later
5. **No hidden controls**  -  every feature is reachable from the Control Center
