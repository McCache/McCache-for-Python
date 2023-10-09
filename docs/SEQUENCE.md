# Communication Protocol

The following are the operation code that are send between nodes to communicate their intent with each other.
|Op Code|Description|
|:------|:----------|
|ACK    |Acknowledgement of a received message.|
|BYE    |Member announcing it is leaving the group.|
|DEL    |Member requesting the group to evict the cache entry.|
|ERR    |Member announcing an error to the group.|
|INI    |Member announcing its initialization to the group.|
|INQ    |Member inquiring about a cache entry from the group.|
|MET    |Member inquiring about the cache metrics from the group.|
|NEW    |New member annoucement to join the group.|
|NAK    |Negative acknowledgement.  Didn't receive the key/value.|
|NOP    |No operation.|
|RAK    |Request acknowledgment for a key.|
|REQ    |Member requesting resend message fragment.|
|RST    |Member requesting reset of the cache.|
|UPD    |Update an existing cache entry (Insert/Update).|

<<<<<<< HEAD
onLY `DEL` and `UPD` will require acknowledgment from the receiving node(s).
=======
only `DEL` and `UPD` will require acknowledgment from the receiving node(s).
>>>>>>> main

## Joining and leaving the cluster.
```mermaid
---
title: McCache protocol to join and leave the cluster.
---
sequenceDiagram
<<<<<<< HEAD
    box lightblue   Machine 1
    participant HS  as Housekeeper
    participant S   as Sender
    end
    box lightgreen  Machine 2
    participant R   as Receiver
    participant HR  as Housekeeper
    end
    S->>R: NEW
    S->>R: BYE
=======
    box MintCream   Machine 1
    participant HS  as Housekeeper
    participant S   as Sender
    end
    box Azure  Machine 2
    participant R   as Receiver
    participant HR  as Housekeeper
    end
    S -) R: NEW
    S -) R: BYE
>>>>>>> main
```

## Insert/Update a value in the cache.
```mermaid
---
title: McCache protocol for inserts and updates.
---
%% SEE: https://www.w3schools.com/tags/ref_colornames.asp
sequenceDiagram
autonumber
    box MintCream   An entry inserted into the cache on Machine 1
        participant H0  as House keeper
        participant P0  as Pending List
        participant R0  as Receiver
        participant S0  as Sender
    end
    box Azure  Machine 2 is the receiver of the cache operation
        participant S1  as Sender
        participant R1  as Receiver
        participant A1  as Assembly List
        participant C1  as Cache
        participant H1  as House keeper
    end

    S0 -->>P0 : Create pending acknowledgement.
    S0  -) R1 : UPD
    R1 -->>A1 : Collect the message fragment(s)

    rect Beige
    alt  Received all fragments
        R1-->>C1 : Insert into the cache
        R1-->>S1 : Queue up the ACK
        S1 -) R0 : ACK
        R0-->>P0 : Remove pending acknowledgement
    else Some missing fragments
        rect HoneyDew
            loop Every 2 seconds
                A1-->>H1 : Check for pending fragments
                rect LightGoldenRodYellow
                opt  Some missing fragments
                    H1-->>S1 : Queue up the REQ for missing fragments
                    break Exceeded maximum retries
                        H1-->>H1 : Log Error
                        H1--X A1 : Remove pending assembly
                    end
                end
                end
            end
        end
    end
    end

    rect LightGoldenRodYellow
    opt  Some missing fragments
        S1 -) R0 : REQ
        P0-->>S0 : Read requested fragments
        S0 -) R1 : UPD (Retransmit requested fragments)
    end
    end

    rect HoneyDew
        loop Every 2 seconds
            P0-->>H0 : Check for pending acknowledgement
            rect LightGoldenRodYellow
            opt  Some unacknowledge messages
                H0-->>S0 : Queue up the RAK for unacknowledge message
            end
            break Exceeded maximum retries
                H0-->>H0 : Log Error
                H0--X P0 : Remove pending acknowledgement
            end
            end
        end
    end

    rect LightGoldenRodYellow
    opt  Some missing fragments
        S0 -) R1 : RAK
        A1-->>R1 : Check for requested fragment
        rect Beige
        alt  Fragment exist
            R1-->>S1 : Queue up the ACK
            S1 -) R0 : ACK
        else Fragment doesn't exist
        end
            R1-->>S1 : Queue up the REQ for missing fragments
            S1 -) R0 : REQ
        end
        break Exceeded maximum retries
            R1-->>R1 : Log Error.
            R1--X A1 : Remove pending assembly
        end
    end
    end
```

## Delete a value in the cache using the key.
```mermaid
---
title: McCache protocol for deletes.
---
%% SEE: https://www.w3schools.com/tags/ref_colornames.asp
sequenceDiagram
autonumber
    box MintCream   An entry inserted into the cache on Machine 1
        participant H0  as House keeper
        participant P0  as Pending List
        participant R0  as Receiver
        participant S0  as Sender
    end
    box Azure  Machine 2 is the receiver of the cache operation
        participant S1  as Sender
        participant R1  as Receiver
        participant C1  as Cache
    end

    S0-->>P0 : Create pending acknowledgement.
    S0 -) R1 : DEL
    R1-->>C1 : Evict the entry from cache
    R1-->>S1 : Queue up the ACK
    S1 -) R0 : ACK
    R0--X P0 : Remove pending acknowledgement

    rect HoneyDew
        loop Every 2 seconds
            P0-->>H0 : Check for pending acknowledgement
            rect LightGoldenRodYellow
            opt  Some unacknowledge messages
                H0-->>S0 : Queue up the RAK for unacknowledge message
            end
            break Exceeded maximum retries
                H0-->>H0 : Log Error
                H0--X P0 : Remove pending acknowledgement
            end
            end
        end
    end

    rect LightGoldenRodYellow
    opt  Some unacknowledge messages
        S0 -) R1 : RAK
        R1-->>C1 : Check for requested message
        R1-->>S1 : Queue up the ACK
    end
    end
```
