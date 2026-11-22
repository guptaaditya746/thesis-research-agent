# Shift from rag-claude-s1-ec928480 to rag-claude-s1-cf-5893772b

Study S001 (paper S001): supports -> contradicts; changed measurements: S001.m1: 0.295 -> 0.168, S001.m2: 0.178 -> 0.202, S001.m9: 0.316 -> 0.229, S001.m10: 0.194 -> 0.285.
Expected label: mixed -> mixed (does not change).

## The changed study's direction

| system          | from     | before       | before_correct   | to          | after        | after_correct   |
|-----------------|----------|--------------|------------------|-------------|--------------|-----------------|
| evidence-engine | supports | undetermined | no               | contradicts | undetermined | no              |
| rag-baseline    | supports | undetermined | no               | contradicts | undetermined | no              |
| agent-baseline  | supports | supports     | yes              | contradicts | contradicts  | yes             |

## The label

| system          | expected_before   | before   | before_correct   | expected_after   | after   | after_correct   | changed   | shifted_as_expected   |
|-----------------|-------------------|----------|------------------|------------------|---------|-----------------|-----------|-----------------------|
| evidence-engine | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | no                    |
| rag-baseline    | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | no                    |
| agent-baseline  | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | yes                   |

shifted_as_expected: the direction before and after and the label before and after are all as predicted.
