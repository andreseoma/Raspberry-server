/*
 * ATmega kood.c
 *
 * Created: 27.05.2016 13:24.55
 * Author : Andres
 */ 

#include <avr/io.h>
#include <avr/power.h>
#include <avr/interrupt.h>

#define RECEIVEBUFFERCOUNT 6
#define RECEIVEBUFFERSIZE 64

char receivedStrings [RECEIVEBUFFERCOUNT][RECEIVEBUFFERSIZE];
uint8_t beginning = 0;
uint8_t end = 0;
uint8_t currentlyReceiving = 0;
uint8_t currentlyReceivingStringOffset = 0;
volatile uint8_t size = 0;
uint8_t receiving = 0;
char currentCommand[64];
uint8_t ID;


ISR(USART_RX_vect){
	//receive data to a circular buffer, beginning points to the first string, end to the next string after the last one
	char c = UDR0;
	receivedStrings[end][currentlyReceivingStringOffset] = c;
	++currentlyReceivingStringOffset;
	if(currentlyReceivingStringOffset == 1 && size == RECEIVEBUFFERCOUNT){
		size -= 1;
		beginning = beginning == RECEIVEBUFFERCOUNT - 1 ? 0 : beginning + 1;
	}
	if(c == '\n'){
		size += 1;
		receivedStrings[end][currentlyReceivingStringOffset] = 0;
		end = end == RECEIVEBUFFERCOUNT - 1 ? 0 : end + 1;
		currentlyReceivingStringOffset = 0;
	}
}

uint8_t getCommand(char* destination){
	cli();
	if(size == 0){
		sei();
		return 0;
	}
	for(uint8_t n = 0; n < RECEIVEBUFFERSIZE; ++n){
		char c = receivedStrings[beginning][n];
		if(c == '\n'){
			destination[n] = 0;
			break;
		}
		destination[n] = receivedStrings[beginning][n];
	}
	size -= 1;
	beginning = beginning == RECEIVEBUFFERCOUNT - 1 ? 0 : beginning + 1;
	sei();
	return 1;
}

uint8_t strcmp(char* string1, char* string2){
	while(1){
		if(*string1 == 0 && *string2 == 0){
			return 0;
		}
		else if (*string1 != *string2){
			return 1;
		}
		string1++;
		string2++;
	}
}

uint8_t startsWith(char* string1, char* string2){
	while(1){
		if(*string2 == 0){
			return 0;
		}
		else if (*string1 != *string2){
			return 1;
		}
		string1++;
		string2++;
	}
}

void sendString(char* string){
	while(1){
		if(*string == 0){
			break;
		}
		while(!(UCSR0A & (1<<UDRE0))){}
		UDR0 = *string;
	}
}

void waitForCommand(char* destination){
	while(1){
		while(size == 0){}
		getCommand(destination);
		if(startsWith(destination, "+IPD") == 0){
			uint8_t commandStart = 0;
			while(destination[commandStart] != ':'){
				commandStart++;
			}
			commandStart++;
			uint8_t n = 0;
			while(destination[commandStart + n] != 0){
				destination[n] = destination[commandStart + n];
			}
			break;
		}
	}
}

void setLeds(char* ledString){
	
}

int main(void)
{
	clock_prescale_set(clock_div_1);
	DDRC = 3;
	PORTC = 3;
	
	UCSR0B = (1<<RXEN0)|(1<<TXEN0)|(1<<RXEN0);
	UCSR0C = (0b11<<UCSZ00);
	UBRR0 = 3;
	
	sendString("AT\r\n");
	for(uint8_t i = 0; i < 3; ++i){
		while(!getCommand(currentCommand));
	}
	
	sendString("AT+CIFSR\r\n");
	for(uint8_t i = 0; i < 5; ++i){
		while(!getCommand(currentCommand));
	}
	
	sendString("AT+CIPSTART=\"TCP\",\"192.168.1.101\",8890\r\n");
	for(uint8_t i = 0; i < 5; ++i){
		while(!getCommand(currentCommand));
	}
	
	char commandBuffer[64] = {0};
	
	waitForCommand(commandBuffer);
	sendString("name=ATMEGA;leds=000\n");
	waitForCommand(commandBuffer);//receiving ID=...
	sendString("OK\n");
	
    while (1) 
    {
		waitForCommand(commandBuffer);
		if(startsWith(commandBuffer, "From")){
			uint8_t commandStart = 0;
			while(commandBuffer[commandStart] != '='){
				commandStart++;
			}
			commandStart++;
			if(startsWith(commandBuffer, "leds")){
				setLeds(commandBuffer + commandStart);
			}
		}
    }
}

