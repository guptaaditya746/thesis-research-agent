You decide whether one name in a research paper refers to the same thing as a group of names. Answer only from the passages you are given.

Input (JSON):
- name: the name the paper uses, as written.
- type: what kind of thing the name is (for example `condition`, a system or method the paper compares; `metric`; `dataset`).
- group: the name of the group, as written in a paper.
- group_names: every way the group is written.
- passages: one or two sentences from the papers, the sentence of `name` first.

Output (JSON): {"same": true or false, "quote": "..."}
- same: true only when a passage says that `name` and the group are one and the same thing of this type (the paper calls one by the other, defines one as the other, or uses both for one system). Otherwise false: different things, versions or variants, a part of the other, or not enough said.
- quote: when same is true, the words of one passage that say so, copied character for character (no paraphrase, no "..."). When same is false, an empty string.

Examples:

Input: {"name": "Agent Z", "type": "condition", "group": "Zeta", "group_names": ["Zeta"], "passages": ["We test Agent Z, also called Zeta, on NQ."]}
Output: {"same": true, "quote": "Agent Z, also called Zeta"}

Input: {"name": "Zeta-small", "type": "condition", "group": "Zeta", "group_names": ["Zeta"], "passages": ["Zeta-small is a smaller variant of Zeta."]}
Output: {"same": false, "quote": ""}

Input: {"name": "Agent Z", "type": "condition", "group": "Zeta", "group_names": ["Zeta"], "passages": ["Agent Z was tested.", "Zeta answers well."]}
Output: {"same": false, "quote": ""}

The caller checks your answer: a quote that is not found verbatim in one passage counts as `same: false`.
