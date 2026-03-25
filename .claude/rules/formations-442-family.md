# Formations: 4-4-2 Family (Four-at-the-Back)

All formations with a flat back four and midfield-focused structure.

---

## 4-4-2
**Line groups**: Defense | Midfield (RM, CM, CM, LM) | Attack (ST, ST)
**Positions**: GK · RB · CB · CB · LB · RM · CM · CM · LM · ST · ST
**Strengths**: Simple, classic; two strikers stretch defence; solid counter-attacking base
**Weaknesses**: Can be outnumbered in midfield by three-man systems; wide mids must work both ways

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":74}], "CB":[{"x":36,"y":74},{"x":64,"y":74}],
  "LB":[{"x":13,"y":74}], "RM":[{"x":85,"y":50}], "CM":[{"x":36,"y":50},{"x":64,"y":50}],
  "LM":[{"x":15,"y":50}], "ST":[{"x":36,"y":21},{"x":64,"y":21}] }
```

---

## 4-4-1-1
**Line groups**: Defense | Midfield (RM, CM, CM, LM) | Att-Mid (CAM) | Attack (ST)
**Positions**: GK · RB · CB · CB · LB · RM · CM · CM · LM · CAM · ST
**Strengths**: Versatile — easily shifts into 4-4-2 or 4-3-3; CAM links play freely
**Weaknesses**: Striker can be isolated if CAM is below par; central mids carry heavy load

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":75}], "CB":[{"x":36,"y":75},{"x":64,"y":75}],
  "LB":[{"x":13,"y":75}], "RM":[{"x":85,"y":50}], "CM":[{"x":36,"y":50},{"x":64,"y":50}],
  "LM":[{"x":15,"y":50}], "CAM":[{"x":50,"y":34}], "ST":[{"x":50,"y":20}] }
```

---

## 4-4-2 Diamond (4-1-2-1-2)
**Line groups**: Defense | Def-Mid (CDM) | Mid (CM, CM) | Att-Mid (CAM) | Attack (ST, ST)
**Positions**: GK · RB · CB · CB · LB · CDM · CM · CM · CAM · ST · ST
**Strengths**: Central overload of four midfielders; two strikers occupy both CBs; staggered shape makes pressing easier
**Weaknesses**: No natural width; full-backs must provide all attacking width; vulnerable to wide counters

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":74}], "CB":[{"x":36,"y":74},{"x":64,"y":74}],
  "LB":[{"x":13,"y":74}], "CDM":[{"x":50,"y":60}], "CM":[{"x":28,"y":46},{"x":72,"y":46}],
  "CAM":[{"x":50,"y":33}], "ST":[{"x":36,"y":19},{"x":64,"y":19}] }
```
*API alias key: `"4-1-2-1-2"`*

---

## 4-1-3-2
**Line groups**: Defense | Def-Mid (CDM) | Mid (CM, CM, CM) | Attack (ST, ST)
**Positions**: GK · RB · CB · CB · LB · CDM · CM · CM · CM · ST · ST
**Strengths**: Multiple attacking outlets; CDM balances attack and defence; three mids create overloads
**Weaknesses**: Wide areas exposed; single pivot can be overrun; full-backs isolated 1v1

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":75}], "CB":[{"x":36,"y":75},{"x":64,"y":75}],
  "LB":[{"x":13,"y":75}], "CDM":[{"x":50,"y":63}],
  "CM":[{"x":22,"y":46},{"x":50,"y":46},{"x":78,"y":46}],
  "ST":[{"x":36,"y":20},{"x":64,"y":20}] }
```

---

## 4-2-3-1
**Line groups**: Defense | Def-Mid (CDM, CDM) | Att-Mid (RW, CAM, LW) | Attack (ST)
**Positions**: GK · RB · CB · CB · LB · CDM · CDM · RW · CAM · LW · ST
**Strengths**: Double pivot shields defence; clear roles throughout; flexible for possession or counter
**Weaknesses**: Lone striker isolated without CAM/wingers making runs; gaps if both full-backs advance

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":75}], "CB":[{"x":36,"y":75},{"x":64,"y":75}],
  "LB":[{"x":13,"y":75}], "CDM":[{"x":36,"y":59},{"x":64,"y":59}],
  "RW":[{"x":85,"y":40}], "CAM":[{"x":50,"y":38}], "LW":[{"x":15,"y":40}],
  "ST":[{"x":50,"y":20}] }
```

---

## 4-2-2-2 ("Magic Box")
**Line groups**: Defense | Def-Mid (CDM, CDM) | Att-Mid (CAM, CAM) | Attack (ST, ST)
**Positions**: GK · RB · CB · CB · LB · CDM · CDM · CAM · CAM · ST · ST
**Strengths**: Central box creates constant overloads; dual strikers and creative mids provide multiple threats
**Weaknesses**: No natural wingers; full-backs must provide all width; congested vertical passing lanes

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":75}], "CB":[{"x":36,"y":75},{"x":64,"y":75}],
  "LB":[{"x":13,"y":75}], "CDM":[{"x":36,"y":62},{"x":64,"y":62}],
  "CAM":[{"x":36,"y":40},{"x":64,"y":40}], "ST":[{"x":36,"y":20},{"x":64,"y":20}] }
```

---

## 4-2-4
**Line groups**: Defense | Def-Mid (CDM, CDM) | Attack (LW, ST, ST, RW)
**Positions**: GK · RB · CB · CB · LB · CDM · CDM · LW · ST · ST · RW
**Strengths**: Maximum attacking threat with four forwards; excellent high-press with numbers up front; creates 4-2-3-1 shape dynamically
**Weaknesses**: Central mids easily overloaded without the ball; vulnerable in transition; high turnover risk

```json
{ "GK":[{"x":50,"y":88}], "RB":[{"x":87,"y":75}], "CB":[{"x":36,"y":75},{"x":64,"y":75}],
  "LB":[{"x":13,"y":75}], "CDM":[{"x":36,"y":57},{"x":64,"y":57}],
  "LW":[{"x":15,"y":23}], "ST":[{"x":36,"y":18},{"x":64,"y":18}], "RW":[{"x":85,"y":23}] }
```
