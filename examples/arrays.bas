' Demonstrates DIM arrays, DATA/READ, and a simple SUB
DIM scores(4) AS INTEGER
DIM i AS INTEGER
DIM total AS INTEGER

DATA 91, 85, 77, 93, 68

FOR i = 0 TO 4
    READ scores(i)
NEXT i

total = 0
FOR i = 0 TO 4
    total = total + scores(i)
NEXT i

PRINT "Scores:"
FOR i = 0 TO 4
    PRINT "  "; scores(i)
NEXT i

PRINT "Average: "; total / 5
