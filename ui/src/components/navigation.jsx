import React, {Component} from 'react';
import {Navbar, Nav, NavItem, Button} from 'react-bootstrap';
import {Link} from 'react-router-dom';
import {LinkContainer} from 'react-router-bootstrap';

class Navigation extends Component {
  render() {
    const username = this.props.userPool.getCurrentUser().getUsername();

    return(
      <Navbar fluid={true}>
        <Navbar.Header>
          <Navbar.Brand>
            The Wheel
          </Navbar.Brand>
        </Navbar.Header>
        <Nav>
          <LinkContainer to="/app">
            <NavItem eventKey={1}>Wheels</NavItem>
          </LinkContainer>
        </Nav>
        <Nav pullRight>
            <NavItem eventKey={3} onClick={this.props.userLogout}>Logout</NavItem>
        </Nav>
        <Navbar.Text pullRight>
          Signed in as: <strong>{username}</strong>
        </Navbar.Text>
      </Navbar>
    )
  }
}

export default Navigation;
