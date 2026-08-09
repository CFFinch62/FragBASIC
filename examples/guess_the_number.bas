' Demonstrates INPUT, RANDOMIZE, and a DO/LOOP UNTIL
RANDOMIZE
DIM target AS INTEGER
DIM guess AS INTEGER
DIM tries AS INTEGER

target = INT(RND * 100) + 1
tries = 0

PRINT "I'm thinking of a number between 1 and 100."

DO
    INPUT "Your guess: "; guess
    tries = tries + 1

    IF guess < target THEN
        PRINT "Too low!"
    ELSEIF guess > target THEN
        PRINT "Too high!"
    ELSE
        PRINT "You got it in "; tries; " tries!"
    END IF
LOOP UNTIL guess = target
