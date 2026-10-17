# Changes on `feature/drag-reorder-stops`

- Intermediate stops can be reordered by dragging: every stop (filled or empty) has a drag handle (⋮⋮) in the search card. The dragged row follows the finger, the rows it passes make room, and the new order is applied on release. This works at any time, also after the stop was confirmed and a route was found (the routes are searched again).
- The handle replaces the small up / down arrow buttons. With the handle focused, ArrowUp / ArrowDown move the stop and keep the focus on it; the label says the stop's position ("Przystanek 2 z 3 ...").
- Dragging while "Optymalna" is selected switches to "Moja kolejność" (a manual move means the user wants their own order).
- The handle is shown only when there are at least 2 stops (nothing to reorder otherwise); start and destination are not draggable.
- Assumptions: a drag of less than half a row changes nothing; empty stop fields can be moved too; no new dependency (pointer events, like the sheet drag).
- `AGENTS.md` updated. The `README.md` setup is unchanged.
