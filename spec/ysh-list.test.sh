## our_shell: ysh
## oils_failures_allowed: 0

#### basic array
var x = :| 1 2 3 |
write len=$[len(x)]
## STDOUT:
len=3
## END

#### string array with command sub, varsub, etc.
shopt -s ysh:all

var x = 1
var a = :| $x $(write hi) 'sq' "dq $x" |
write len=$[len(a)]
write @a
## STDOUT:
len=4
1
hi
sq
dq 1
## END

#### Can print type of List with pp

var b = :|true|  # this is a string
pp line (b)

# = b

var empty = :||
pp line (empty)

# = empty

## STDOUT:
(List)   ["true"]
(List)   []
## END

#### splice and stringify array

shopt -s parse_at

var x = :| 'a b' c |

declare -a array=( @x )

argv.py "${array[@]}"  # should work

echo -$array-  # fails because of strict_arraywith type error

echo -$x-  # fails with type error

## status: 1
## STDOUT:
['a b', 'c']
## END

#### List->extend()
var l = list(1..3)
echo $[len(l)]
call l->extend(list(3..6))
echo $[len(l)]
## STDOUT:
2
5
## END

#### List append()/extend() should return null
shopt -s oil:all
var l = list(1..3)

var result = l->extend(list(3..6))
call assert_(result === null)

setvar result = l->append(6)
call assert_(result === null)

echo pass
## STDOUT:
pass
## END

#### List pop()
shopt -s oil:all
var l = list(1..5)
call assert_(l->pop() === 4)
call assert_(l->pop() === 3)
call assert_(l->pop() === 2)
call assert_(l->pop() === 1)
echo pass
## STDOUT:
pass
## END
