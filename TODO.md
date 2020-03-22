# Things to fix or change

-   Make all functions return similar stuff.  Right now some return json, some
    request responses, and some who knows what else.

-   All functions should raise HTTPError when request fails

-   Implement some sort of generic canvas call that will make it easy to do
    things that are not yet implemented in specific functions.  It probably
    already mostly exists.
