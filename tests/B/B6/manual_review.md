# B6 command-sense review

Manual review of the first command/action in the 50 B1 responses. Marked sensible when it gives an executable, concept-directed first search or inspection step; generic inventory commands and prose without an actionable command are not sensible. This is a by-eye rating, not a second-model score. Source responses: `../B1/thinking-8192.jsonl` and `../B1/no-thinking-8192.jsonl`.

| ID | Thinking on | Thinking off |
|---|---:|---:|
| t01 | yes | yes |
| t02 | no | no |
| t03 | yes | yes |
| t04 | yes | yes |
| t05 | yes | yes |
| t06 | yes | yes |
| t07 | no | no |
| t08 | yes | yes |
| t09 | yes | yes |
| t10 | yes | yes |
| t11 | yes | yes |
| t12 | yes | yes |
| t13 | yes | yes |
| t14 | no | no |
| t15 | yes | yes |
| t16 | yes | yes |
| t17 | yes | yes |
| t18 | yes | yes |
| t19 | no | no |
| t20 | yes | yes |
| t21 | yes | yes |
| t22 | yes | yes |
| t23 | yes | yes |
| t24 | yes | yes |
| t25 | yes | yes |
| t26 | no | no |
| t27 | yes | yes |
| t28 | no | yes |
| t29 | yes | yes |
| t30 | yes | yes |
| t31 | no | no |
| t32 | no | no |
| t33 | yes | yes |
| t34 | yes | yes |
| t35 | yes | yes |
| t36 | yes | yes |
| t37 | no | no |
| t38 | no | no |
| t39 | yes | no |
| t40 | yes | yes |
| t41 | yes | yes |
| t42 | yes | yes |
| t43 | yes | yes |
| t44 | yes | no |
| t45 | yes | yes |
| t46 | yes | yes |
| t47 | no | yes |
| t48 | yes | yes |
| t49 | yes | yes |
| t50 | yes | no |

Sensible rate: 39/50 (78%) thinking on, 38/50 (76%) thinking off. Mean response latency: 7.74 s on, 7.54 s off. Mean parsed reasoning tokens: 988 on, 958 off. The command-sense difference is negligible relative to the formatting failure; the main harness need is robust handling of prose-only and unfenced commands.
