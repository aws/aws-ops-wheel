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

import React, {PureComponent} from 'react';
import PropTypes from 'prop-types';
import ReactDOM from 'react-dom';
import connect from 'react-redux-fetch';
import {Button, Modal} from 'react-bootstrap';
import {WheelType, ParticipantType} from '../types';
import {LinkWrapper, WHEEL_COLORS, apiURL, staticURL, getAuthHeaders} from '../util';
import {usePermissions} from './PermissionContext';
import '../static_content/wheel_click.mp3';
import 'isomorphic-fetch';
import * as PIXI from 'pixi.js';

// Mathematical Constants
const QUARTER_CIRCLE = Math.PI / 2;
const FULL_CIRCLE = Math.PI * 2;
const DEGREES_TO_RADIANS = Math.PI / 180;
const HALF_CIRCLE = Math.PI;
const DEFAULT_ROTATIONS = 20;
const DEGREES_IN_CIRCLE = 360;

// Canvas and Drawing Constants
const CANVAS_SIZE = 1000;
const CANVAS_CENTER = CANVAS_SIZE / 2;
const INNER_RADIUS = 10;
const OUTER_RADIUS = CANVAS_SIZE / 2;
const TEXT_RADIUS = OUTER_RADIUS - 15;
const TEXT_WORD_WRAP_RATIO = 0.8;
const BASE_FONT_SIZE = 16;
const FONT_SIZE_MULTIPLIER = 80;

// Canvas Colors and Styling
const CANVAS_BACKGROUND_COLOR = 0xFAFAFA;
const WHEEL_BORDER_COLOR = '#FAFAFA';
const ARROW_COLOR = '#FF9900';
const COLOR_PALETTE_SIZE = 16;

// Animation Constants
const EASE_OUT_FRAMES = 125;
const LINEAR_FRAMES = 125;
const RIGGING_PAUSE_FRAMES = 50;
const MIN_FRAMES_BETWEEN_CLICKS = 5;

// Text and Participant Constants
const MAX_PARTICIPANT_NAME_LENGTH = 32;
const MIN_PARTICIPANT_NAME_LENGTH = 4;
const FIXED_TRUNCATION_MAX_PARTICIPANTS = 50;
const TRUNCATION_INCREMENT = 2;
const TRUNCATION_STEP = 5;
const ELLIPSIS = '...';
const ELLIPSIS_LENGTH = 3;

// Audio Constants
const AUDIO_VOLUME = 1;
const AUDIO_RESET_TIME = 0;
const AUDIO_MIME_TYPE = 'audio/mpeg';
const AUDIO_FILE = 'wheel_click.mp3';

// UI Layout Constants
const BUTTON_HEIGHT = '38px';
const WHEEL_SIZE_VMIN = '75vmin';
const WHEEL_RADIUS_VMIN = '37.5vmin';
const SPIN_BUTTON_SIZE = '10vmin';
const SPIN_BUTTON_RADIUS = '5vmin';
const ARROW_SIZE = '2vmin';
const ARROW_WIDTH = '4vmin';
const BORDER_SIZE = '1vmin';
const SPIN_BUTTON_FONT_SIZE = '2vmin';
const BUTTON_GAP = '10px';
const BUTTON_MARGIN = '5px';

// Local Storage Keys
const STORAGE_KEYS = {
  IS_MUTED: 'isMuted'
};

// Permission Constants
const REQUIRED_PERMISSIONS = {
  MANAGE_PARTICIPANTS: 'manage_participants'
};

// Error Messages
const ERROR_MESSAGES = {
  WHEEL_LOAD_ERROR: 'Error: Wheel or wheel participants could not be loaded!',
  PARTICIPANT_SELECT_ERROR: 'Error: Participant Selection could not be loaded!',
  AUDIO_PLAY_ERROR: 'Audio play failed:',
  AUDIO_ERROR: 'Audio error:'
};

// Loading and UI Messages
const UI_MESSAGES = {
  LOADING_WHEEL: 'Loading the Wheel and its Participants...',
  NO_PARTICIPANTS: "You don't have any participants!",
  EDIT_PARTICIPANTS: 'Edit participants',
  CHOOSE: 'Choose',
  SPIN: 'Spin',
  SOUND_ON: '🔊',
  SOUND_OFF: '🔇'
};

// Animation Configuration
const ANIMATION_CONFIG = {
  EASE_OUT_MULTIPLIER: -3,
  LINEAR_RANDOM_OFFSET: 0.5,
  RIGGED_CENTER_OFFSET: 0
};

// CSS Styles as Constants
const STYLES = {
  pageRoot: {
    textAlign: 'center',
    position: 'relative'
  },
  loadingContainer: {
    padding: '15px'
  },
  titleContainer: {
    position: 'relative'
  },
  noParticipantsWarning: {
    display: 'inline-flex'
  },
  controlsContainer: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '0 0 10px 0'
  },
  soundButton: {
    position: 'absolute',
    left: '1em',
    height: BUTTON_HEIGHT,
    display: 'flex',
    alignItems: 'center'
  },
  buttonsContainer: {
    textAlign: 'center',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: BUTTON_GAP
  },
  rightSideControls: {
    position: 'absolute',
    right: '20px',
    top: '50%',
    transform: 'translateY(-50%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '15px',
    zIndex: 200
  },
  multiSelectContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '12px 16px',
    border: '2px solid #007bff',
    borderRadius: '8px',
    backgroundColor: '#ffffff',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    minWidth: '200px'
  },
  multiSelectInput: {
    width: '60px',
    padding: '6px 10px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    fontSize: '14px'
  },
  editButton: {
    margin: BUTTON_MARGIN,
    height: BUTTON_HEIGHT,
    display: 'flex',
    alignItems: 'center'
  },
  chooseButton: {
    margin: BUTTON_MARGIN,
    height: BUTTON_HEIGHT,
    display: 'flex',
    alignItems: 'center'
  },
  wheelContainer: {
    position: 'relative'
  },
  arrow: {
    position: 'absolute',
    height: '0',
    width: '0',
    fontSize: '0',
    borderTop: `${ARROW_SIZE} solid transparent`,
    borderBottom: `${ARROW_SIZE} solid transparent`,
    borderLeft: `${ARROW_WIDTH} solid ${ARROW_COLOR}`,
    top: `calc(${WHEEL_RADIUS_VMIN} - ${ARROW_SIZE})`,
    right: `calc(50vw + ${WHEEL_RADIUS_VMIN})`
  },
  canvas: {
    position: 'absolute',
    top: 0,
    left: `calc(50vw - ${WHEEL_RADIUS_VMIN})`,
    height: WHEEL_SIZE_VMIN,
    width: WHEEL_SIZE_VMIN,
    overflow: 'hidden',
    borderRadius: '50%'
  },
  spinButton: {
    position: 'absolute',
    top: `calc(${WHEEL_RADIUS_VMIN} - ${SPIN_BUTTON_RADIUS})`,
    left: `calc(50vw - ${SPIN_BUTTON_RADIUS})`,
    height: SPIN_BUTTON_SIZE,
    width: SPIN_BUTTON_SIZE,
    borderRadius: '50%',
    border: `${BORDER_SIZE} solid ${WHEEL_BORDER_COLOR}`,
    overflow: 'hidden',
    padding: 0,
    zIndex: 100,
    fontSize: SPIN_BUTTON_FONT_SIZE,
    textAlign: 'center'
  }
};

// Debug Configuration
const DEBUG_CONFIG = {
  ENABLE_WHEEL_FETCH_DEBUG: true,
  ENABLE_SUGGEST_DEBUG: true,
  ENABLE_SPIN_DEBUG: true
};

/**
 * Ease out function for spin animation
 * @param currentTime   Current time
 * @param startAngle   Starting angle
 * @param incrementAngle   Change in angle
 * @param duration   Total Duration
 * @returns {number}  Angle to be at at this point in time
 */
function easeOut(currentTime, startAngle, incrementAngle, duration) {
  let multiplier = (currentTime /= duration) * currentTime;
  let increment = multiplier * currentTime;
  return startAngle + incrementAngle * (increment + ANIMATION_CONFIG.EASE_OUT_MULTIPLIER * multiplier + 3 * currentTime);
}

/**
 * Linear easing function for spin animation
 * @param currentTime   Current time
 * @param startAngle   Starting angle
 * @param incrementAngle   Change in angle
 * @param duration   Total Duration
 * @returns {number}  Angle to be at at this point in time
 */
function linear(currentTime, startAngle, incrementAngle, duration) {
  return incrementAngle * currentTime / duration + startAngle;
}

/**
 * Permission-aware EditParticipantsButton component
 * Only shows for users with manage_participants permission (WHEEL_ADMIN and ADMIN)
 */
const EditParticipantsButton = ({ wheelId }) => {
  const { hasPermission, loading } = usePermissions();
  
  if (loading) {
    return null; // Don't show anything while loading permissions
  }
  
  // Only show the button if user has manage_participants permission
  if (!hasPermission('manage_participants')) {
    return null;
  }
  
  return (
    <LinkWrapper to={`wheel/${wheelId}/participant`} style={{ margin: '5px' }}>
      <Button size='md' style={{height: '38px', display: 'flex', alignItems: 'center'}}>
        Edit participants
      </Button>
    </LinkWrapper>
  );
};

/**
 * The Wheel component
 */
export class Wheel extends PureComponent {
  constructor(props) {
    super(props);

    this.storage = global.window.localStorage;

    this.state = {
      wheel: undefined,
      participants: undefined,
      isSpinning: false,
      fetching: true,
      rigExtra: undefined,
      isMuted: (this.storage.getItem(STORAGE_KEYS.IS_MUTED) === 'true' ? true : false),
      isMultiSelect: false,
      multiSelectCount: 2,
      selectedParticipants: [],
      showResultsModal: false,
    };
    this.lastSector = 0;
  }

  componentDidMount() {
    // Ensure clean state on mount (especially after navigation)
    this.resetMultiSelectState();
    this.fetchWheelAndParticipants();
    // Fetch the wheel click MP3 for later playback
    fetch(staticURL('wheel_click.mp3'), { headers: {'Accept': 'audio/mpeg'} })
      .then(response => response.blob())
      .then(result => this.setState({clickUrl: window.URL.createObjectURL(result)}))
      .catch(err => console.error('Failed to load wheel click audio:', err));
  }

  componentWillUnmount() {
    if (this.application !== undefined) {
      this.application.ticker.stop();
      this.application.stop();
      this.application.destroy();
    }
  }

  /**
   * Reset all multi-select related state to ensure clean state after navigation
   */
  resetMultiSelectState() {
    this.setState({
      isMultiSelect: false,
      multiSelectCount: 2,
      selectedParticipants: [],
      selectedParticipant: undefined,
      showResultsModal: false,
      isSpinning: false
    });
  }

  fetchWheelAndParticipants() {
    this.props.dispatchWheelGet(this.props.match.params.wheel_id);
    this.props.dispatchAllParticipantsGet(this.props.match.params.wheel_id);
    this.setState({fetching: true});
  }

  componentDidUpdate() {
    const {wheelFetch, allParticipantsFetch, participantSuggestFetch, multiSuggestFetch} = this.props;

    // Process gets for the wheel and participant data and draw the wheel
    if (wheelFetch.fulfilled && allParticipantsFetch.fulfilled && this.state.fetching) {
      // We precompute and set up some canvas settings beforehand so they don't need fresh calculations every render
      // V2 API returns wheel with participants included, or participants as separate array
      const participants = wheelFetch.value.participants || allParticipantsFetch.value.participants || allParticipantsFetch.value || [];

      this.setState({
        participants: participants,
        wheel: wheelFetch.value,
        fetching: false,
        sectorSize: Math.PI * 2 / participants.length,
        rigExtra: Math.max(QUARTER_CIRCLE, Math.PI * 2 / participants.length),
        }, this.drawInitialWheel);
    }

    // Process multi-select result - only if we're actually in multi-select mode
    if (this.state.isSpinning && this.state.selectedParticipants.length === 0 && this.state.isMultiSelect && multiSuggestFetch?.fulfilled) {
      const apiResponse = multiSuggestFetch.value;
      const selectedParticipants = apiResponse.selected_participants || [];
      
      // For multi-select, we don't animate the wheel, just show results in modal
      this.setState({
        selectedParticipants: selectedParticipants,
        isSpinning: false,
        showResultsModal: true
      });
    }

    // Process single-select result and spin the wheel
    if (this.state.isSpinning && this.state.selectedParticipant === undefined && participantSuggestFetch.fulfilled && !this.state.isMultiSelect) {
      const {participants} = this.state;
      
      // Extract selected participant from API response (v2 API structure)
      const apiResponse = participantSuggestFetch.value;
      let selectedParticipant = apiResponse.selected_participant || apiResponse;
      const isRigged = apiResponse.rigged || selectedParticipant.rigged;
      
      // This gives us a random point in the sector for the selection to land
      let selectedIndex = Math.random() - 0.5;
      // Let's make it stop exactly in the middle for rigged wheels
      if (isRigged)
        selectedIndex = 0;
      // Get the selected participant's index
      for (let participant of participants) {
        if (participant.participant_id === selectedParticipant.participant_id) {
          selectedParticipant = Object.assign({}, selectedParticipant, participant, { rigged: isRigged });
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
    const fontSize = BASE_FONT_SIZE + (FONT_SIZE_MULTIPLIER / participants.length);
    const renderelement = ReactDOM.findDOMNode(this.refs.canvas);

    this.application = new PIXI.Application({
       width: CANVAS_SIZE,
       height: CANVAS_SIZE,
       view: renderelement,
       antialias: true,
       backgroundColor: CANVAS_BACKGROUND_COLOR,
    });

    this.spinTicker = this.application.ticker;
    this.wheelGraphic = new PIXI.Container();
    const graphics = new PIXI.Graphics();
    this.wheelGraphic.x = CANVAS_CENTER;
    this.wheelGraphic.y = CANVAS_CENTER;
    this.wheelGraphic.addChild(graphics);

    // If the wheel is too crowded, dynamically truncate the participant names based on the number of participants
    let maxParticipantNameLength = MAX_PARTICIPANT_NAME_LENGTH;
    if(participants.length > FIXED_TRUNCATION_MAX_PARTICIPANTS) {
      for (let i = participants.length; i > FIXED_TRUNCATION_MAX_PARTICIPANTS; i -= TRUNCATION_STEP) {
        maxParticipantNameLength -= TRUNCATION_INCREMENT;
        if(maxParticipantNameLength <= MIN_PARTICIPANT_NAME_LENGTH)
          break;
      }
    }

    for (let i in participants) {
      i = parseInt(i);
      graphics.moveTo(0, 0);
      graphics.beginFill(parseInt(WHEEL_COLORS[i % COLOR_PALETTE_SIZE].replace('#', '0x')));
      graphics.arc(0, 0, OUTER_RADIUS, (i - 0.5) * sectorSize + HALF_CIRCLE, (i + 0.5) * sectorSize + HALF_CIRCLE);
      graphics.endFill();
      graphics.closePath();

      let textPositionAngle = sectorSize * i - Math.atan(-0.5 * fontSize / OUTER_RADIUS) + HALF_CIRCLE;
      let participantName = participants[i].participant_name;
      if(participantName.length > maxParticipantNameLength) {
        // Name should not exceed maximum length (minus 3 characters for the ellipsis)
        participantName = participantName.substring(0, (maxParticipantNameLength - ELLIPSIS_LENGTH)) + ELLIPSIS;
      }
      let basicText = new PIXI.Text(participantName, {fontSize});
      basicText.style.wordWrap = true;
      basicText.style.wordWrapWidth = TEXT_RADIUS * TEXT_WORD_WRAP_RATIO;
      basicText.style.align = 'center';

      basicText.x = TEXT_RADIUS * Math.cos(textPositionAngle);
      basicText.y = TEXT_RADIUS * Math.sin(textPositionAngle);
      basicText.rotation = sectorSize * i;

      this.wheelGraphic.addChild(basicText);
    }

    // random start location so that specific projects don't always see their name at the starting point
    // Note that this does not change the selection of the project (i.e. the project that the wheel
    // points to at first load is still not selected)
    this.wheelGraphic.rotation = (Math.random() * DEGREES_IN_CIRCLE) * DEGREES_TO_RADIANS;

    this.application.stage.addChild(this.wheelGraphic);
  }

  // Renders the initial wheel
  drawWheel = (offset=0, time=undefined) => {
    this.wheelGraphic.rotation = offset;
    const currentSector = Math.floor(offset / this.state.sectorSize - 0.5);
    if (currentSector !== this.lastSector && time !== undefined) {
      if (this.lastClickTime === undefined || time - this.lastClickTime > MIN_FRAMES_BETWEEN_CLICKS) {
        // Only try to play sound if audio URL is loaded and sound is not muted
        if (this.state.clickUrl && this.refs.clickSound && !this.state.isMuted) {
          try {
            this.refs.clickSound.volume = 1;
            this.refs.clickSound.currentTime = 0;
            this.refs.clickSound.play().catch(err => console.log('Audio play failed:', err));
          } catch (err) {
            console.log('Audio error:', err);
          }
        }
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
    if (this.state.isSpinning || this.props.participantSelectFetch.pending || this.props.multiSuggestFetch?.pending) {
      return;
    }
    
    // Capture the current multi-select state before clearing other state
    const isMultiSelectMode = this.state.isMultiSelect;
    const multiSelectCount = this.state.multiSelectCount;
    
    // Clear previous selections and modal state
    this.setState({
      selectedParticipant: undefined, 
      selectedParticipants: [],
      showResultsModal: false,
      isSpinning: true
    });

    // Use multi-select or single-select API based on captured checkbox state
    if (isMultiSelectMode) {
      // For multi-select, don't apply weight changes during spin - just get selections
      this.props.dispatchMultiSuggestPost(this.props.match.params.wheel_id, multiSelectCount, false);
    } else {
      this.props.dispatchParticipantSuggestPost(this.props.match.params.wheel_id);
    }
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
    if (time < 0) {
      this.lastClickTime = 0;
      return;
    }
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
   * Opens the selected Participant's Web Page(s)
   */
  openParticipantPage = () => {
    // If already spinning, do nothing
    if (this.state.isSpinning) {
      return;
    }

    if (this.state.selectedParticipant) {
      // Single-select mode: open single participant's URL
      this.props.dispatchParticipantSelectPost(this.props.match.params.wheel_id, this.state.selectedParticipant.participant_id);
      window.open(this.state.selectedParticipant.participant_url);
    }
  }

  /**
   * Opens a single participant's page (for individual buttons in multi-select modal)
   */
  openSingleParticipantPage = (participant) => {
    if (this.state.isSpinning) {
      return;
    }
    this.props.dispatchParticipantSelectPost(this.props.match.params.wheel_id, participant.participant_id);
    window.open(participant.participant_url);
  }

  /**
   * Opens all selected participants' pages with proper timing to avoid popup blockers
   * First applies weight redistribution, then opens URLs
   */
  openAllParticipantPages = () => {
    if (this.state.isSpinning) {
      return;
    }
    
    // First, apply weight redistribution by calling the multi-suggest API with apply_changes: true
    this.props.dispatchMultiSuggestApplyChangesPost(
      this.props.match.params.wheel_id, 
      this.state.selectedParticipants.length
    );
    
    // Open URLs with small delays to avoid popup blockers
    // Note: We don't call dispatchParticipantSelectPost here because the multi-selection
    // was already recorded when the multi-suggest API was called during spinning
    this.state.selectedParticipants.forEach((participant, index) => {
      setTimeout(() => {
        window.open(participant.participant_url);
      }, index * 100); // 100ms delay between each window
    });
  }

  toggleSound = () => {

    var newMuted = !this.state.isMuted;

    this.setState({isMuted: newMuted});
    this.storage.setItem(STORAGE_KEYS.IS_MUTED, newMuted);

    this.refs.clickSound.volume = (!newMuted ? AUDIO_VOLUME : AUDIO_RESET_TIME);
  }

  /**
   * Handle multi-select checkbox change
   */
  handleMultiSelectChange = (event) => {
    const isMultiSelect = event.target.checked;
    this.setState({
      isMultiSelect,
      selectedParticipants: [], // Clear previous selections when toggling
      selectedParticipant: undefined,
      showResultsModal: false // Clear modal state when switching modes
    });
  }

  /**
   * Handle multi-select count input change
   */
  handleMultiSelectCountChange = (event) => {
    const count = parseInt(event.target.value) || 2;
    const maxCount = Math.min(50, this.state.participants ? this.state.participants.length : 50);
    const validCount = Math.max(1, Math.min(count, maxCount));
    
    this.setState({
      multiSelectCount: validCount
    });
  }

  /**
   * Close the results modal
   */
  closeResultsModal = () => {
    this.setState({ showResultsModal: false });
  }

  /**
   * Render multi-select results modal
   */
  renderMultiSelectModal = () => {
    const { selectedParticipants, showResultsModal } = this.state;
    
    if (!showResultsModal || selectedParticipants.length === 0) {
      return null;
    }

    return (
      <Modal show={showResultsModal} onHide={this.closeResultsModal} size="lg" centered>
        <Modal.Header closeButton>
          <Modal.Title>
            Selected Participants ({selectedParticipants.length})
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div style={{
            maxHeight: '400px',
            overflowY: 'auto'
          }}>
            {selectedParticipants.map((participant, index) => (
              <div key={participant.participant_id || index} style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '12px 16px',
                marginBottom: '8px',
                backgroundColor: '#f8f9fa',
                border: '1px solid #dee2e6',
                borderRadius: '6px',
                fontSize: '14px'
              }}>
                <span style={{
                  fontWeight: '500',
                  flex: 1,
                  textAlign: 'left'
                }}>
                  {participant.participant_name}
                </span>
                <Button 
                  variant="primary" 
                  size="sm"
                  onClick={() => this.openSingleParticipantPage(participant)}
                  style={{
                    marginLeft: '12px',
                    minWidth: '80px'
                  }}
                >
                  Choose
                </Button>
              </div>
            ))}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={this.closeResultsModal}>
            Close
          </Button>
          <Button variant="primary" onClick={this.openAllParticipantPages} size="lg">
            Choose All Participants
          </Button>
        </Modal.Footer>
      </Modal>
    );
  }

  render() {
    const {wheelFetch, allParticipantsFetch, participantSuggestFetch} = this.props;
    const {wheel, participants, isSpinning, selectedParticipant, isMuted, isMultiSelect, selectedParticipants} = this.state;

    let participantName;
    let chooseButtonText = UI_MESSAGES.CHOOSE;
    let chooseButtonDisabled = true;

    if (isMultiSelect && selectedParticipants.length > 0) {
      chooseButtonText = `Choose ${selectedParticipants.length} Participants`;
      chooseButtonDisabled = false;
    } else if (selectedParticipant !== undefined && !isSpinning) {
      participantName = selectedParticipant.participant_name;
      chooseButtonDisabled = false;
    }

    let header;
    if (wheel === undefined || participants === undefined) {
      if (wheelFetch.rejected || allParticipantsFetch.rejected) {
        header = <div>{ERROR_MESSAGES.WHEEL_LOAD_ERROR}</div>;
      } else if (participantSuggestFetch.rejected) {
        header = <div>{ERROR_MESSAGES.PARTICIPANT_SELECT_ERROR}</div>;
      } else {
        header = <div style={STYLES.loadingContainer}>{UI_MESSAGES.LOADING_WHEEL}</div>;
      }
    } else {
      header = <div style={STYLES.titleContainer}>
        <h1 className='title'>
          <div className='title-text'>{wheel.wheel_name || wheel.name}</div>
        </h1>
        <h3 style={{display: participants.length === 0 ? 'inline-flex' : 'none'}}>
          {UI_MESSAGES.NO_PARTICIPANTS}
        </h3>
      </div>;
    }

    return (
      <div className='pageRoot' style={STYLES.pageRoot}>
        <audio ref='clickSound'
               preload='auto'
               src={this.state.clickUrl}
               type={AUDIO_MIME_TYPE} />
        {header}
        <div style={STYLES.controlsContainer}>
          <Button
            id='btnSoundToggle'
            onClick={this.toggleSound}
            ref='btnSoundToggle'
            size='md'
            style={STYLES.soundButton}
          >
            {isMuted ? UI_MESSAGES.SOUND_OFF : UI_MESSAGES.SOUND_ON}
          </Button>
          <div style={STYLES.buttonsContainer}>
            <EditParticipantsButton wheelId={this.props.match.params.wheel_id} />

            <Button variant='primary' size='md' disabled={chooseButtonDisabled} onClick={this.openParticipantPage}
            style={STYLES.chooseButton}>
                {isMultiSelect && selectedParticipants.length > 0 ? chooseButtonText : (
                  <>{UI_MESSAGES.CHOOSE}{participantName && <>&nbsp;<b>{participantName}</b></>}</>
                )}
            </Button>
          </div>
          
          {/* Right side controls */}
          <div style={STYLES.rightSideControls}>
            <div style={STYLES.multiSelectContainer}>
              <label>
                <input
                  type="checkbox"
                  checked={this.state.isMultiSelect}
                  onChange={this.handleMultiSelectChange}
                  style={{ marginRight: '6px' }}
                />
                Multi-Select
              </label>
              <input
                type="number"
                min="1"
                max={Math.min(50, participants ? participants.length : 50)}
                value={this.state.multiSelectCount}
                onChange={this.handleMultiSelectCountChange}
                disabled={!this.state.isMultiSelect}
                style={STYLES.multiSelectInput}
              />
            </div>
          </div>
        </div>
        <div style={STYLES.wheelContainer}>
          <span style={STYLES.arrow}/>
          <canvas ref='canvas' width={CANVAS_SIZE} height={CANVAS_SIZE} style={STYLES.canvas} />
          <Button variant='primary' disabled={isSpinning || participants === undefined || participants.length === 0}
            id='btnSpin'
            style={STYLES.spinButton} 
            onClick={this.startSpinningWheel}>
            {UI_MESSAGES.SPIN}
          </Button>
        </div>
        {this.renderMultiSelectModal()}
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
        url: apiURL(`wheels/${wheelId}`),
        headers: getAuthHeaders(),
      })
    },
    {
      resource: 'allParticipants',
      method: 'get',
      request: (wheelId)  => ({
        url: apiURL(`wheels/${wheelId}/participants`),
        headers: getAuthHeaders(),
      })
    },
    {
      resource: 'participantSelect',
      method: 'post',
      request: (wheelId, participantId)  => ({
        url: apiURL(`wheels/${wheelId}/participants/${participantId}/select`),
        headers: getAuthHeaders(),
      })
    },
    {
      resource: 'participantSuggest',
      method: 'post',
      request: (wheelId)  => ({
        url: apiURL(`wheels/${wheelId}/suggest`),
        headers: getAuthHeaders(),
      })
    },
    {
      resource: 'multiSuggest',
      method: 'post',
      request: (wheelId, count, applyChanges = true)  => ({
        url: apiURL(`wheels/${wheelId}/multi-suggest`),
        headers: getAuthHeaders(),
        body: JSON.stringify({
          count: count,
          apply_changes: applyChanges
        })
      })
    },
    {
      resource: 'multiSuggestApplyChanges',
      method: 'post',
      request: (wheelId, count)  => ({
        url: apiURL(`wheels/${wheelId}/multi-suggest`),
        headers: getAuthHeaders(),
        body: JSON.stringify({
          count: count,
          apply_changes: true
        })
      })
    },
  ]
) (Wheel);
