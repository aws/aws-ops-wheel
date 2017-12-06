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
import ReactDOM from 'react-dom';
import connect from 'react-redux-fetch';
import {RouteComponentProps} from 'react-router';
import {Button} from 'react-bootstrap';
import {WheelType, ParticipantType} from '../types';
import {LinkWrapper, WHEEL_COLORS, apiURL, staticURL} from '../util';
import '../static_content/wheel_click.mp3';
import 'isomorphic-fetch';
import * as PIXI from 'pixi.js';


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
  rigExtra: number | undefined,
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
const TEXT_RADIUS = OUTER_RADIUS - 15;
const EASE_OUT_FRAMES = 300;
const LINEAR_FRAMES = 300;
const RIGGING_PAUSE_FRAMES = 50;
const MIN_FRAMES_BETWEEN_CLICKS = 9;


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
      rigExtra: undefined,
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

  componentWillUnmount() {
    if (this.application !== undefined) {
      this.application.ticker.stop();
      this.application.stop();
      this.application.destroy();
    }
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
        rigExtra: Math.max(QUARTER_CIRCLE, Math.PI * 2 / allParticipantsFetch.value.length),
        }, this.drawInitialWheel);
    }

    // Process suggested participant result and spin the wheel
    if (this.state.isSpinning && this.state.selectedParticipant === undefined && participantSuggestFetch.fulfilled) {
      const {participants} = this.state;
      let selectedParticipant = participantSuggestFetch.value;
      // This gives us a random point in the sector for the selection to land
      let selectedIndex = Math.random() - 0.5;
      // Let's make it stop exactly in the middle for rigged wheels
      if (selectedParticipant.rigged)
        selectedIndex = 0;
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
      }, () => this.spinTicker.add(this.spin)
    );
    }
  }

  drawInitialWheel() {
    const {participants, sectorSize} = this.state;
    const fontSize = 16 + (80 / participants.length);
    const renderelement = ReactDOM.findDOMNode(this.refs.canvas);
    this.application = new PIXI.Application({
       width: CANVAS_SIZE,
       height: CANVAS_SIZE,
       view: renderelement,
       antialias: true,
       backgroundColor: 0xFAFAFA,
    });
    this.spinTicker = this.application.ticker;
    this.wheelGraphic = new PIXI.Container();
    const graphics = new PIXI.Graphics();
    this.wheelGraphic.x = CANVAS_SIZE / 2;
    this.wheelGraphic.y = CANVAS_SIZE / 2;
    this.wheelGraphic.addChild(graphics);
    // ctx.translate(this.refs.canvas.width / 2, this.refs.canvas.width / 2);
    // ctx.font = `bold ${16 + 80 / participants.length}px Helvetica`;
    for (let i in participants) {
      i = parseInt(i);
      graphics.moveTo(0, 0);
      graphics.beginFill(parseInt(WHEEL_COLORS[i % 16].replace('#', '0x')));
      graphics.arc(0, 0, OUTER_RADIUS, (i - 0.5) * sectorSize + Math.PI, (i + 0.5) * sectorSize + Math.PI);
      graphics.endFill();
      graphics.closePath();
      let textPositionAngle = sectorSize * i - Math.atan(-0.5 * fontSize / OUTER_RADIUS) + Math.PI;
      let basicText = new PIXI.Text(participants[i].name, {fontSize});
      basicText.x = TEXT_RADIUS * Math.cos(textPositionAngle);
      basicText.y = TEXT_RADIUS * Math.sin(textPositionAngle);
      basicText.rotation = sectorSize * i;
      this.wheelGraphic.addChild(basicText);
    }
    this.application.stage.addChild(this.wheelGraphic);
  }

  // Renders the initial wheel
  drawWheel = (offset=0, time=undefined) => {
    this.wheelGraphic.rotation = offset;
    const currentSector = Math.floor(offset / this.state.sectorSize - 0.5);
    if (currentSector !== this.lastSector && time !== undefined) {
      if (this.lastClickTime === undefined || time - this.lastClickTime > MIN_FRAMES_BETWEEN_CLICKS) {
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

  spin = (delta) => {
    if (this.currentAnimationTime === undefined) {
      this.currentAnimationTime = 0;
      this.lastClickTime = 0;
    }
    const time = this.currentAnimationTime += delta;
    let {selectedParticipant, targetAngle, rigExtra} = this.state;
    if (selectedParticipant.rigged)
      targetAngle += rigExtra;  // Overshoot because we'll go back to them
    const currentAngle = easeOut(this.currentAnimationTime, 0, targetAngle, EASE_OUT_FRAMES);
    if (currentAngle >= targetAngle) {
      this.spinTicker.remove(this.spin);
      if (selectedParticipant.rigged) {
        this.drawWheel(targetAngle, time);
        this.currentAnimationTime = 0;
        this.spinTicker.add(this.riggedSpin);
      } else {
        this.drawWheel(targetAngle, time);
        this.setState({isSpinning: false, targetAngle: undefined});
        this.currentAnimationTime = undefined;
      }
    } else {
      this.drawWheel(currentAngle, time);
    }
  }

  riggedSpin = (delta) => {
    // Don't render at more than 60fps
    const time = (this.currentAnimationTime += delta) - RIGGING_PAUSE_FRAMES;
    if (time < 0)
      this.lastClickTime = 0;
      return;
    const {targetAngle, rigExtra} = this.state;
    const currentAngle = linear(time, targetAngle + rigExtra, -rigExtra, LINEAR_FRAMES);
    if (currentAngle <= targetAngle) {
      this.spinTicker.remove(this.riggedSpin);
      this.drawWheel(targetAngle, time);
      this.setState({isSpinning: false, targetAngle: undefined});
      this.currentAnimationTime = undefined;
    } else {
      this.drawWheel(currentAngle, time);
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
      header = <div style={{position: 'relative'}}>
        <div style={{fontSize: '3vmin', textAlign: 'center', 'width': '100%'}}>
          {wheel.name}
        </div>
        <h3 style={{display: participants.length === 0 ? 'inline-flex' : 'none'}}>
          You don't have any partcipants!
        </h3>
      </div>;
    }

    return (
      <div className='pageRoot' style={{textAlign: 'center'}}>
        <audio ref='clickSound'
               preload='auto'
               src={this.state.clickUrl}
               type='audio/mpeg' />
        {header}
        <div style={{textAlign: 'center', display: 'flex', justifyContent: 'space-around'}}>
          <LinkWrapper to={`wheel/${this.props.match.params.wheel_id}/participant`} style={{
            margin: '5px'
          }}>
            <Button>Edit participants</Button>
          </LinkWrapper>
          <Button bsStyle='primary' bsSize='large' disabled={participantName === undefined}   onClick={this.openParticipantPage}
          style={{margin: '5px'}}>
              Choose  <b>{participantName}</b>
          </Button>
        </div>
        <div style={{
          display: participants !== undefined && participants.length > 0 ? 'block' : 'none',
          position: 'relative'
        }}>
          <span style={{
            position: 'absolute',
            height: '0',
            width: '0',
            fontSize: '0',
            borderTop: '2vmin solid transparent',
            borderBottom: '2vmin solid transparent',
            borderLeft: '4vmin solid #FF9900',
            top: 'calc(40vmin - 2vmin)',
            right: 'calc(50vw + 40vmin)',
           }}/>
          <canvas ref='canvas' width={CANVAS_SIZE} height={CANVAS_SIZE}
            style={{
              position: 'absolute',
              top: 0,
              left: 'calc(50vw - 40vmin)',
              height: '80vmin',
              width: '80vmin',
              overflow: 'hidden',
              borderRadius: '50%',
            }} />
          <Button bsStyle='primary' disabled={isSpinning || participants === undefined || participants.length === 0}
            style={{
            position: 'absolute',
            top: 'calc(40vmin - 5vmin)',
            left: 'calc(50vw - 5vmin)',
            height: '10vmin',
            width: '10vmin',
            borderRadius: '50%',
            border: '1vmin solid #FAFAFA',
            overflow: 'hidden',
            padding: 0,
            zIndex: 100,
            fontSize: '2vmin',
            textAlign: 'center',
            }} onClick={this.startSpinningWheel}>
            Spin
          </Button>
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
