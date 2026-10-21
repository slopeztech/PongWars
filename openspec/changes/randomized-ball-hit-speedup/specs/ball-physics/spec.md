# Spec Delta

## Purpose

Defines ball movement and speed progression so rallies remain playable while paddle-hit behavior stays reproducible across matches.

## ADDED Requirements

### Requirement: Randomized speed increase on ordinary paddle hits
The system SHALL increase ball speed by a randomly selected factor from 1.01 through 1.04 on each ordinary paddle hit, using the match seed so identical initial configurations and input sequences produce identical results.

#### Scenario: Ordinary hit applies a bounded random increase
- **WHEN** an ordinary paddle hit occurs below the maximum ball speed
- **THEN** the outgoing ball speed is increased by a factor between 1.01 and 1.04, inclusive

#### Scenario: Identical seeded matches remain deterministic
- **WHEN** two matches have the same seed and receive the same input sequence
- **THEN** ordinary paddle hits apply the same speed increases in both matches

### Requirement: Special hit boosts and maximum speed remain unchanged
The system SHALL preserve the existing spin and headbutt speed boosts and SHALL NOT allow a paddle hit to increase the ball above the existing maximum speed.

#### Scenario: Special paddle hits retain their boosts
- **WHEN** a spin or headbutt hit occurs
- **THEN** its existing special speed boost is used instead of the ordinary randomized increase

#### Scenario: Paddle hit respects the maximum speed
- **WHEN** any paddle hit would increase the ball above the maximum speed
- **THEN** the outgoing ball speed does not exceed that maximum
