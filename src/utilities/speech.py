from typing import List, Optional

from jstools.screeps import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


def translate_lyrics(input_str):
    # type: (str) -> List[Optional[str]]
    result = []
    next_lyric = []
    for char in input_str:
        if char is '\n' or char is ' ':
            if len(next_lyric):
                result.push(''.join(next_lyric))
                next_lyric = []
            if char is '\n':
                result.push(None)
        else:
            next_lyric.push(char)
    if len(next_lyric):
        result.push(''.join(next_lyric))
    return result


we_are_miners = translate_lyrics("""
We are miners, hard rock miners
To the shaft house we must go
Pour your bottles on our shoulders
We are marching to the slow

On the line boys, on the line boys
Drill your holes and stand in line
'til the shift boss comes to tell you
You must drill her out on top

Can't you feel the rock dust in your lungs?
It'll cut down a miner when he is still young
Two years and the silicosis takes hold
and I feel like I'm dying from mining for gold

Yes, I feel like I'm dying from mining for gold
""")

wolf = translate_lyrics("""
The modern wolf
He's kinder
But see him weep
It's a reminder
Don't wear no suits
We're talking t-shirts
See how he glides
Makes women shiver

Ahoooooo, Ahoooooo

He ain't no Jack
His voice is smoother
Been bending notes
Just like his father
Ahooo but no birds or beasts does he eat
He only wants the tenderest meat
And oh the sounds he makes them speak
Under all different patterns of sheets
Colors blind
Oh, dopamine
And she looked so good when they were last seen

Ahoooooo, Ahoooooo

The modern wolf, the modern wolf
Dripping in all the lives that he took
He'll go on home
Try to wash them off
But when he shaves he hears them call

Ahoooooo, Ahoooooo
""")

h_s_t_k = translate_lyrics("""
I've got a television it's filling with home
I've got a television it's filling with home
Wherever I end up wherever I roam
Hey I've got a television it's filling with home
I've got a phone that beeps, let's me know I'm not alone
I've got a phone that beeps, let's me know I'm not alone
Wherever I end up I sleep like a stone, yeah
I've got a phone that beeps, let's me know I'm not alone

My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They're running everywhere in fancy clothes
My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They take me to where I want to go

Bright
Oh, young
Kinda hurt
Don't you wanna get some
Esso
Bright
Young
Hurt
Don't you wanna get some

My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They're running everywhere in fancy clothes
My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They take me to where I need to go

All around the party, we stand in circles numb
Yeah, all around the party, we stand in circles numb
Oh, who can I find here, who knows where I come from
All around the party we stand in circles numb
I had a thread before now I don't know where it's gone
I had a thread before now I don't know where it's gone
Oh, how did I get here did it say when I was young
I had a thread before now I don't know where it's gone

I've got a television it's filling with home
I've got a television it's filling with home
Wherever I end up wherever I roam
Hey I've got a television it's filling with home

Bright
Oh, young
Kinda hurt
Don't you wanna get some
Esso
Bright
Young
Hurt
Don't you wanna get some,

Wanna get, wanna get, wanna get...

Some, some, some, some

Wanna get, wanna get, wanna get...

Some, some, some, some

My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They're running everywhere in fancy clothes
My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They take me to where I need to go

My head my shoulders knees and toes
My head my shoulders knees and toes
My head my shoulders knees and toes
They're running everywhere in fancy clothes
My head my shoulders knees and toes
My head my shoulders knees and toes
Head my shoulders knees and toes
They take me to where I need to go
""")

breeze_blocks = translate_lyrics("""
She may contain the urge to run away
But hold her down with soggy clothes and breezeblocks
Cetirizine your fever's gripped me again
Never kisses— -all you ever send are full stops, la, la, la

Do you know where the wild things go?
They go along to take your honey, la, la, la
Break down, now weep,
Build up breakfast, now let's eat
My love, my love, love, love, la, la, la

Muscle to muscle and toe to toe
The fear has gripped me but here I go
My heart sinks as I jump up
Your hand grips hand as my eyes shut

Do you know where the wild things go?
They go along to take your honey, la, la, la
Break down, now sleep
Build up breakfast, now let's eat
My love my love, love, love

She bruises, coughs, she splutters pistol shots
Hold her down with soggy clothes and breezeblocks
She's morphine, queen of my vaccine
My love, my love, love, love, la, la, la

Muscle to muscle and toe to toe
The fear has gripped me but here I go
My heart sinks as I jump up
Your hand grips hand as my eyes shut

She may contain the urge to run away
But hold her down with soggy clothes and breezeblocks
Germolene, disinfect the scene
My love, my love, love, love
But please don't go, I love you so, my lovely

Please don't go, please don't go
I love you so, I love you so
Please don't go, please don't go
I love you so, I love you so
Please break my heart, hey

Please don't go, please don't go
I love you so, I love you so
Please don't go, please don't go
I love you so, I love you so
Please break my heart

Please don't go, I'll eat you whole
I love you so, I love you so, I love you so
Please don't go I'll eat you whole
I love you so, I love you so, I love you so, I love you so

I'll eat you whole
I love you so, I love you so
I'll eat you whole
I love you so, I love you so

I'll eat you whole
I love you so, I love you so
Please don't go, I'll eat you whole
I love you so, I love you so, I love you so
Please don't go, I'll eat you whole
I love you so, I love you so, I love you so
""")

tessellate = translate_lyrics("""
Bite chunks out of me
You're a shark and I'm swimming
My heart still thumps as I bleed
And all your friends come sniffing

Triangles are my favorite shape
Three points where two lines meet
Toe to toe, back to back, let's go, my love; it's very late
'Til morning comes, let's tessellate

Go alone my flower
And keep my whole lovely you
Wild green stones alone my lover
And keep us on my heart

Three guns and one goes off
One's empty, one's not quick enough
One burn, one red, one grin
Search the graves while the camera spins

Chunks of you will sink down to seals
Blubber rich in mourning, they'll nosh you up
Yes, they'll nosh the love away but it's fair to say
You will still haunt me

Triangles are my favorite shape
Three points where two lines meet
Toe to toe, back to back, let's go my love; it's very late
'Til morning comes, let's tessellate
""")

songs = {
    'a': breeze_blocks,
    'm': we_are_miners,
    'w': wolf,
    'h': h_s_t_k,
    't': tessellate
}
