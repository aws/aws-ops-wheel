/*
 * Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *   http://aws.amazon.com/apache2.0/
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */

import React, {PureComponent, PropTypes} from 'react';
import connect from 'react-redux-fetch';
import {RouteComponentProps} from 'react-router';
import {Button} from 'react-bootstrap';
import {WheelType, ParticipantType} from '../types';
import {WHEEL_COLORS, apiURL, staticURL, LinkWrapper} from '../util';
import '../static_content/wheel_click.mp3';
import 'isomorphic-fetch';

interface WheelDispatchProps {
  dispatchWheelGet: PropTypes.func.isRequired,
  wheelFetch: PropTypes.object,
  dispatchAllParticipantsGet: PropTypes.func.isRequired,
  allParticipantsFetch: PropTypes.object,
  dispatchParticipantSelectPost: PropTypes.func.isRequired,
  participantSelectFetch: PropTypes.object,
  dispatchParticipantSuggestGet: PropTypes.func.isRequired,
  participantSuggestFetch: PropTypes.object,
}

interface WheelState {
  wheel: undefined | WheelType,
  participants: undefined | ParticipantType[],
  isSpinning: boolean,
  fetching: boolean,
}

type WheelProps = WheelDispatchProps & RouteComponentProps<{ wheelID: string }>;


const QUARTER_CIRCLE = Math.PI / 2;

/**
 * Ease out function for spin animation
 * @param currentTime   Current time
 * @param startAngle   Starting angle
 * @param incrementAngle   Change in angle
 * @param duration   Total Duration
 * @returns {number}  Angle to be at at this point in time
 */
function easeOut(currentTime: number, startAngle: number, incrementAngle: number, duration: number) {
  let multiplier = (currentTime /= duration) * currentTime;
  let increment = multiplier * currentTime;
  return startAngle + incrementAngle * (increment + -3 * multiplier + 3 * currentTime);
}

/**
 * Linear easing function for spin animation
 * @param currentTime   Current time
 * @param startAngle   Starting angle
 * @param incrementAngle   Change in angle
 * @param duration   Total Duration
 * @returns {number}  Angle to be at at this point in time
 */
function linear(currentTime: number, startAngle: number, incrementAngle: number, duration: number) {
  return incrementAngle * currentTime / duration + startAngle;
}


const CANVAS_SIZE = 1000;
const INNER_RADIUS = 10;
const OUTER_RADIUS = CANVAS_SIZE / 2;
const TEXT_RADIUS = OUTER_RADIUS - 30;


/**
 * The Wheel component
 */
export class Wheel extends PureComponent<WheelProps, WheelState> {
  constructor(props: WheelProps) {
    super(props);
    this.state = {
      wheel: undefined,
      participants: undefined,
      isSpinning: false,
      fetching: true,
    };
    this.lastSector = 0;
  }

  componentDidMount() {
    this.fetchWheelAndParticipants();
    // Fetch the wheel click MP3 for later playback
    fetch(staticURL('wheel_click.mp3'), { headers: {'Accept': 'audio/mpeg'} })
      .then(response => response.blob())
      .then(result => this.setState({clickUrl: window.URL.createObjectURL(result)})).catch(err => console.log(err));
  }

  fetchWheelAndParticipants() {
    this.props.dispatchWheelGet(this.props.match.params.wheel_id);
    this.props.dispatchAllParticipantsGet(this.props.match.params.wheel_id);
    this.setState({fetching: true});
  }

  componentDidUpdate() {
    const {wheelFetch, allParticipantsFetch, participantSuggestFetch} = this.props;

    // Process gets for the wheel and participant data and draw the wheel
    if (wheelFetch.fulfilled && allParticipantsFetch.fulfilled && this.state.fetching) {
      // We precompute and set up some canvas settings beforehand so they don't need fresh calculations every render

      this.setState({
        participants: allParticipantsFetch.value,
        wheel: wheelFetch.value,
        fetching: false,
        sectorSize: Math.PI * 2 / allParticipantsFetch.value.length,
        }, this.drawInitialWheel);
    }

    // Process suggested participant result and spin the wheel
    if (this.state.selectedParticipant === undefined && participantSuggestFetch.fulfilled) {
      const {participants} = this.state;
      let selectedParticipant = participantSuggestFetch.value;
      // This gives us a random point in the sector for the selection to land
      let selectedIndex = Math.random();
      // Let's make it stop exactly in the middle for rigged wheels
      if (selectedParticipant.rigged)
        selectedIndex = 0.5;
      // Get the selected participant's index
      for (let participant of participants) {
        if (participant.id === selectedParticipant.participant_id) {
          selectedParticipant = Object.assign({}, selectedParticipant, participant);
          break;
        }
        selectedIndex++;
      }
      // 10 rotations and then adjusted to select a particular participant
      this.setState({
        targetAngle: (20 * Math.PI) - (this.state.sectorSize * selectedIndex),
        selectedParticipant
      }, () => window.requestAnimationFrame(this.spin)
    );
    }
  }

  drawInitialWheel() {
    const {participants, sectorSize} = this.state;
    const halfSector = Math.PI / participants.length;
    const ctx = this.refs.canvas.getContext('2d');
    ctx.translate(this.refs.canvas.width / 2, this.refs.canvas.width / 2);
    ctx.font = `bold ${16 + 80 / participants.length}px Helvetica`;
    ctx.strokeStyle = 'black';
    ctx.lineWidth = 3;
    // Save the initial rotation angle so it can be restored after drawing to keep rotation angles consistent
    ctx.save()
    // Draw each of the sectors
    ctx.rotate(halfSector - Math.PI);
    for (let i in participants) {
      ctx.beginPath();
      ctx.arc(0, 0, OUTER_RADIUS, -halfSector, halfSector, false);
      ctx.arc(0, 0, INNER_RADIUS, halfSector, -halfSector, true);
      ctx.closePath();
      ctx.fillStyle = WHEEL_COLORS[i % 16];
      ctx.fill();
      // Position and draw text within the segment.  We flip it upside down so we can preserve the positioning but write from the outside of the circle inwards.
      ctx.rotate(Math.PI)
      ctx.fillStyle = 'black';
      ctx.fillText(participants[i].name, -TEXT_RADIUS, 5);
      // Flip right-side up and rotate to next sector
      ctx.rotate(Math.PI + sectorSize);
    }
    ctx.restore()
  }

  // Renders the initial wheel
  drawWheel = (offset=0, time=undefined) => {
    const {sectorSize, isSpinning} = this.state;
    this.refs.canvas.style.transform = `rotate(${offset}rad)`;
    const currentSector = Math.floor(offset / sectorSize);
    if (currentSector !== this.lastSector && time !== undefined) {
      if (this.lastClickTime === undefined || time - this.lastClickTime > 150) {
        this.refs.clickSound.currentTime = 0;
        this.refs.clickSound.play();
        this.lastClickTime = time;
      }
    }
    this.lastSector = currentSector;
  }

  /**
   * When the spin button is clicked
   */
  startSpinningWheel = () => {
    // If already spinning or we have stuff in flight, do nothing
    if (this.state.isSpinning || this.props.participantSelectFetch.pending) {
      return;
    }
    this.setState({selectedParticipant: undefined, isSpinning: true});
    this.props.dispatchParticipantSuggestGet(this.props.wheelFetch.value.id);
  }

  spin = (time) => {
    if (this.startTime === undefined) {
      this.startTime = time;
      this.lastTime = time;
    }
    // Don't render at more than 60fps
    if (time - this.lastTime < 16) {
      return window.requestAnimationFrame(this.spin);
    }
    this.lastTime = time;
    let targetAngle = this.state.targetAngle;
    if (this.state.selectedParticipant.rigged)
      targetAngle += QUARTER_CIRCLE;  // Overshoot because we'll go back to them
    const currentAngle = easeOut(time - this.startTime, 0, targetAngle, 5000);
    if (currentAngle >= targetAngle) {
      if (this.state.selectedParticipant.rigged) {
        this.drawWheel(targetAngle, time);
        this.startTime = time + 500;
        window.requestAnimationFrame(this.riggedSpin);
      } else {
        this.drawWheel(targetAngle, time);
        this.setState({isSpinning: false, targetAngle: undefined});
        this.startTime = undefined;
      }
    } else {
      this.drawWheel(currentAngle, time);
      window.requestAnimationFrame(this.spin);
    }
  }

  riggedSpin = (time) => {
    // Don't render at more than 60fps
    if (time < this.startTime || time - this.lastTime < 16 ) {
      return window.requestAnimationFrame(this.riggedSpin);
    }
    this.lastTime = time;
    const currentAngle = linear(time - this.startTime, this.state.targetAngle + QUARTER_CIRCLE, -QUARTER_CIRCLE, 3000);
    if (currentAngle <= this.state.targetAngle) {
      this.drawWheel(this.state.targetAngle, time);
      this.setState({isSpinning: false, targetAngle: undefined});
      this.startTime = undefined;
    } else {
      this.drawWheel(currentAngle, time);
      window.requestAnimationFrame(this.riggedSpin);
    }
  }

  /**
   * Opens the selected Participant's Web Page
   */
  openParticipantPage = () => {
    // If already spinning, do nothing
    if (this.state.isSpinning) {
      return;
    }

    // POST the selected participant (this also un-rigs the wheel)
    this.props.dispatchParticipantSelectPost(this.state.selectedParticipant.wheel_id, this.state.selectedParticipant.id);

    // Open the participant's URL
    window.open(this.state.selectedParticipant.url);
  }

  render() {
    const {wheelFetch, allParticipantsFetch, participantSuggestFetch} = this.props;
    const {wheel, participants, isSpinning, selectedParticipant} = this.state;

    let participantName;
    if (selectedParticipant !== undefined && !isSpinning) {
      participantName = selectedParticipant.name;
    }

    let header;
    if (wheel === undefined || participants === undefined) {
      if (wheelFetch.rejected || allParticipantsFetch.rejected) {
        header = <div>Error: Wheel or wheel participants could not be loaded!</div>;
      } else if (participantSuggestFetch.rejected) {
        header = <div>Error: Participant Selection could not be loaded!</div>;
      } else {
        header = <div style={{padding: '15px'}}>Loading the Wheel and its Participants...</div>;
      }
    } else {
      header = <div>
        <div style={{fontSize: '3vmin', textAlign: 'center'}}>
          {wheel.name}
        </div>
        <h3 style={{display: participants.length === 0 ? 'inline-flex' : 'none'}}>
          You don't have any partcipants!
        </h3>
      </div>;
    }

    return (
      <div className='pageRoot' style={{textAlign: 'center'}}>
        <LinkWrapper to={`wheel/${this.props.match.params.wheel_id}/participant`} style={{
          position: 'absolute',
          top: '60px',
          left: '10px',
        }}>
          <Button>Edit participants</Button>
        </LinkWrapper>
        <audio ref='clickSound'
               preload='auto'
               src={this.state.clickUrl}
               type='audio/mpeg' />
        {header}
        <div style={{display: participants !== undefined && participants.length > 0 ? 'block' : 'none'}}>
          <Button bsStyle='primary' disabled={isSpinning || participants === undefined || participants.length === 0}
            style={{
            position: 'absolute',
            top: 'calc(90px + 31.5vmin)',
            left: 'calc(50vw - 5vmin)',
            height: '10vmin',
            width: '10vmin',
            borderRadius: '50%',
            border: '1vmin solid #FAFAFA',
            overflow: 'hidden',
            zIndex: 0,
            fontSize: '2vmin',
            }} onClick={this.startSpinningWheel}>Spin</Button>
          <span style={{
            position: 'absolute',
            top: 'calc(90px + 33.5vmin)',
            right: 'calc(50vw + 32.5vmin)',
            textAlign: 'right',
            display: 'flex',
          }}>
            <Button bsStyle='primary' bsSize='large' disabled={participantName === undefined} onClick={this.openParticipantPage} style={{
              position: 'relative',
              textAlign: 'right',
              margin: '5px',
              height: '5vmin',
              fontSize: '2vmin',
              verticalAlign: 'middle',
            }}>
                Choose  <b>{participantName}</b>
            </Button>
            <span style={{
              height: '0',
              width: '0',
              fontSize: '0',
              float: 'right',
              position: 'relative',
              borderTop: '2vmin solid transparent',
              borderBottom: '2vmin solid transparent',
              borderLeft: '4vmin solid #FF9900',
              justifyContent: 'center',
              flexDirection: 'column',
              alignSelf: 'center',
            }}/>
          </span>
          <canvas ref='canvas' width={CANVAS_SIZE} height={CANVAS_SIZE}
            style={{
              position: 'absolute',
              top: 'calc(90px + 4vmin)',
              left: 'calc(50vw - 32.5vmin)',
              height: '65vmin',
              width: '65vmin',
              overflow: 'hidden',
              borderRadius: '50%',
              zIndex: -1,
            }} />
        </div>
      </div>
    );
  }
}

export default connect(
  [
    {
      resource: 'wheel',
      method: 'get',
      request: (wheelId)  => ({
        url: apiURL(`wheel/${wheelId}`),
      })
    },
    {
      resource: 'allParticipants',
      method: 'get',
      request: (wheelId)  => ({
        url: apiURL(`wheel/${wheelId}/participant`),
      })
    },
    {
      resource: 'participantSelect',
      method: 'post',
      request: (wheelId, participantId)  => ({
        url: apiURL(`wheel/${wheelId}/participant/${participantId}/select`),
      })
    },
    {
      resource: 'participantSuggest',
      method: 'get',
      request: (wheelId)  => ({
        url: apiURL(`wheel/${wheelId}/participant/suggest`),
      })
    },
  ]
) (Wheel);
